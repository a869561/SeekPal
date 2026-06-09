"""Orquestador de indexación: extractor → chunker → embedder → vector store.

Ofrece dos modos:
- index_file()      — indexa un único fichero (usado por tests y llamadas puntuales)
- prepare_file()
  + store_prepared() — modo batch: separar extracción/chunking del embedding para
                       poder embeddear todos los chunks de todos los ficheros de una
                       fuente en una sola llamada, reduciendo round-trips.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client.http.models import SparseVector

from app.services.rag.chunking_service import chunk_text
from app.services.rag.embedding_service import EmbeddingService, SparseEmbeddingService
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.extractors.registry import get_extractor
from app.services.rag.image_service import extract_image_text_async
from app.services.rag.types import Chunk, ExtractedDoc
from app.services.rag.vector_service import VectorService


def _extractor_name(extractor: BaseExtractor) -> str:
    return extractor.__class__.__name__.removesuffix("Extractor").lower()


@dataclass(slots=True)
class IndexResult:
    status: str
    chunks: int
    extractor: str | None
    error: str | None = None
    indexed_at: datetime | None = None


@dataclass(slots=True)
class PreparedFile:
    """Resultado de prepare_file(): texto extraído y troceado, listo para embeddear."""
    file_id: str
    source_id: str
    file_name: str
    category: str
    extension: str
    chunks: list[Chunk] = field(default_factory=list)
    extractor: str | None = None
    error: str | None = None

    @property
    def skipped(self) -> bool:
        return not self.chunks


def _build_points(
    file_id: str,
    source_id: str,
    file_name: str,
    category: str,
    extension: str,
    chunks: list[Chunk],
    dense_vectors: list[list[float]],
    sparse_vectors: list[SparseVector],
) -> list[tuple]:
    return [
        (
            f"{file_id}::{c.chunk_idx}",
            dense,
            sparse,
            {
                "chunk_id": f"{file_id}::{c.chunk_idx}",
                "file_id": file_id,
                "source_id": source_id,
                "text": c.text,
                "page": c.page,
                "offset_start": c.offset_start,
                "offset_end": c.offset_end,
                "category": category,
                "extension": extension,
                "file_name": file_name,
            },
        )
        for c, dense, sparse in zip(chunks, dense_vectors, sparse_vectors)
    ]


class IndexService:
    def __init__(
        self,
        embedding: EmbeddingService,
        sparse_embedding: SparseEmbeddingService,
        vector: VectorService,
        chunk_size: int,
        overlap: int,
    ):
        self._embedding = embedding
        self._sparse = sparse_embedding
        self._vector = vector
        self._chunk_size = chunk_size
        self._overlap = overlap

    # ------------------------------------------------------------------
    # Single-file API (used by tests and one-off calls)
    # ------------------------------------------------------------------

    async def index_file(
        self,
        file_id: str,
        source_id: str,
        file_name: str,
        category: str,
        extension: str,
        path: Path,
    ) -> IndexResult:
        prep = await self.prepare_file(file_id, source_id, file_name, category, extension, path)
        if prep.skipped:
            status = "failed" if prep.error and not prep.error.startswith(("empty", "no chunks", "skipped")) else "skipped"
            return IndexResult(status=status, chunks=0, extractor=prep.extractor, error=prep.error)

        texts = [c.text for c in prep.chunks]
        try:
            dense_vecs, sparse_vecs = await asyncio.gather(
                self._embedding.embed_texts(texts),
                self._sparse.embed_texts(texts),
            )
        except Exception as exc:
            return IndexResult(status="failed", chunks=0, extractor=prep.extractor, error=f"embedding: {exc}")

        return await self.store_prepared(prep, dense_vecs, sparse_vecs)

    # ------------------------------------------------------------------
    # Batch API (used by scanner for bulk ingestion)
    # ------------------------------------------------------------------

    async def prepare_file(
        self,
        file_id: str,
        source_id: str,
        file_name: str,
        category: str,
        extension: str,
        path: Path,
    ) -> PreparedFile:
        """Extract text and chunk — no embedding yet."""
        extractor = get_extractor(extension, category, path=path)
        if extractor is None:
            return PreparedFile(file_id, source_id, file_name, category, extension, error="skipped")

        ext_name = _extractor_name(extractor)

        try:
            if category == "image":
                # Ruta async: OCR + captioning en paralelo con timeouts independientes.
                # asyncio.wait_for puede cancelar genuinamente (AsyncClient +
                # asyncio.Semaphore), eliminando los timeouts en cascada entre
                # imágenes del mismo grupo causados por threads zombi.
                text = await extract_image_text_async(path)
                doc = ExtractedDoc(text=text, page_map=[], extractor="image")
            else:
                doc = await asyncio.to_thread(extractor.extract, path)
        except Exception as exc:
            return PreparedFile(file_id, source_id, file_name, category, extension,
                                extractor=ext_name, error=f"extraction: {exc}")

        if not doc.text.strip():
            return PreparedFile(file_id, source_id, file_name, category, extension,
                                extractor=ext_name, error="empty text")

        chunks = chunk_text(doc, self._chunk_size, self._overlap)
        if not chunks:
            return PreparedFile(file_id, source_id, file_name, category, extension,
                                extractor=ext_name, error="no chunks produced")

        return PreparedFile(file_id, source_id, file_name, category, extension,
                            chunks=chunks, extractor=ext_name)

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Embed denso de una lista plana de textos."""
        return await self._embedding.embed_texts(texts)

    async def embed_sparse_batch(self, texts: list[str]) -> list[SparseVector]:
        """Embed sparse (BM25) de una lista plana de textos."""
        return await self._sparse.embed_texts(texts)

    async def store_prepared(
        self,
        prep: PreparedFile,
        dense_vectors: list[list[float] | None],
        sparse_vectors: list[SparseVector],
    ) -> IndexResult:
        """Almacena chunks pre-embeddeados en Qdrant. Omite None (NaN fallback)."""
        valid = [
            (c, d, s)
            for c, d, s in zip(prep.chunks, dense_vectors, sparse_vectors)
            if d is not None
        ]
        if not valid:
            return IndexResult(status="failed", chunks=0, extractor=prep.extractor,
                               error="all chunks failed embedding (NaN)")

        valid_chunks, valid_dense, valid_sparse = zip(*valid)
        try:
            await asyncio.to_thread(self._vector.delete_by_file, prep.file_id)
            points = _build_points(
                prep.file_id, prep.source_id, prep.file_name,
                prep.category, prep.extension,
                list(valid_chunks), list(valid_dense), list(valid_sparse),
            )
            await asyncio.to_thread(self._vector.upsert, points)
        except Exception as exc:
            return IndexResult(status="failed", chunks=0, extractor=prep.extractor,
                               error=f"vector store: {exc}")

        return IndexResult(
            status="done",
            chunks=len(valid_chunks),
            extractor=prep.extractor,
            indexed_at=datetime.now(UTC),
        )
