from __future__ import annotations

import os
from pathlib import Path

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models.config import Config
from app.models.file import FileDoc
from app.models.source import Source
from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.index_service import IndexService
from app.services.rag.vector_service import VectorService


_client: AsyncIOMotorClient | None = None
_vector_service: VectorService | None = None
_embedding_service: EmbeddingService | None = None
_index_service: IndexService | None = None

QDRANT_COLLECTION = "seekpal_chunks"
EMBEDDING_DIM = 1024


def _resolve_qdrant_path() -> str:
    raw = settings.qdrant_path
    if os.path.isabs(raw):
        return raw
    # Anclar a backend/ (parent del package app, parent de core/)
    backend_root = Path(__file__).resolve().parent.parent.parent
    return str((backend_root / raw).resolve())


async def connect_database() -> None:
    global _client, _vector_service, _embedding_service, _index_service
    _client = AsyncIOMotorClient(settings.mongo_uri)
    db = _client[settings.mongo_db]
    await init_beanie(database=db, document_models=[Config, Source, FileDoc])

    qdrant_abs = _resolve_qdrant_path()
    _vector_service = VectorService(
        path=qdrant_abs,
        collection=QDRANT_COLLECTION,
        dim=EMBEDDING_DIM,
    )
    _vector_service.ensure_collection()

    _embedding_service = EmbeddingService(
        base_url=settings.ollama_url,
        model=settings.embedding_model,
        batch_size=settings.rag_embed_batch,
    )

    _index_service = IndexService(
        embedding=_embedding_service,
        vector=_vector_service,
        chunk_size=settings.rag_chunk_size,
        overlap=settings.rag_chunk_overlap,
    )

    return qdrant_abs


async def disconnect_database() -> None:
    global _client, _vector_service, _embedding_service, _index_service
    if _vector_service is not None:
        try:
            _vector_service.close()
        except Exception:
            pass
        _vector_service = None
    _embedding_service = None
    _index_service = None
    if _client is not None:
        _client.close()
        _client = None


def is_connected() -> bool:
    return _client is not None


def get_vector_service() -> VectorService:
    if _vector_service is None:
        raise RuntimeError("VectorService no inicializado")
    return _vector_service


def get_embedding_service() -> EmbeddingService:
    if _embedding_service is None:
        raise RuntimeError("EmbeddingService no inicializado")
    return _embedding_service


def get_index_service() -> IndexService:
    if _index_service is None:
        raise RuntimeError("IndexService no inicializado")
    return _index_service
