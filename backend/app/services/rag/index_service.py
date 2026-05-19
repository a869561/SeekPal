"""Orquestador de indexación: extractor → chunker → embedder → vector store."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.rag.chunking_service import chunk_text
from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.extractors.registry import get_extractor
from app.services.rag.types import Chunk
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


class IndexService:
    def __init__(
        self,
        embedding: EmbeddingService,
        vector: VectorService,
        chunk_size: int,
        overlap: int,
    ):
        self._embedding = embedding
        self._vector = vector
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def index_file(
        self,
        file_id: str,
        source_id: str,
        file_name: str,
        category: str,
        extension: str,
        path: Path,
    ) -> IndexResult:
        extractor = get_extractor(extension, category)
        if extractor is None:
            return IndexResult(status="skipped", chunks=0, extractor=None)

        ext_name = _extractor_name(extractor)

        try:
            doc = await asyncio.to_thread(extractor.extract, path)
        except Exception as exc:
            return IndexResult(
                status="failed", chunks=0, extractor=ext_name,
                error=f"extraction: {exc}",
            )

        if not doc.text.strip():
            return IndexResult(
                status="skipped", chunks=0, extractor=ext_name,
                error="empty text",
            )

        chunks: list[Chunk] = chunk_text(doc, self._chunk_size, self._overlap)
        if not chunks:
            return IndexResult(
                status="skipped", chunks=0, extractor=ext_name,
                error="no chunks produced",
            )

        try:
            vectors = await self._embedding.embed_texts([c.text for c in chunks])
        except Exception as exc:
            return IndexResult(
                status="failed", chunks=0, extractor=ext_name,
                error=f"embedding: {exc}",
            )

        if len(vectors) != len(chunks):
            return IndexResult(
                status="failed", chunks=0, extractor=ext_name,
                error="vector count mismatch",
            )

        try:
            await asyncio.to_thread(self._vector.delete_by_file, file_id)
            points = [
                (
                    f"{file_id}::{c.chunk_idx}",
                    vec,
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
                for c, vec in zip(chunks, vectors)
            ]
            await asyncio.to_thread(self._vector.upsert, points)
        except Exception as exc:
            return IndexResult(
                status="failed", chunks=0, extractor=ext_name,
                error=f"vector store: {exc}",
            )

        return IndexResult(
            status="done",
            chunks=len(chunks),
            extractor=ext_name,
            indexed_at=datetime.now(UTC),
        )
