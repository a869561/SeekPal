from __future__ import annotations

from app.services.rag.embedding_service import EmbeddingService, SparseEmbeddingService
from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_service import VectorService


class RetrievalService:
    def __init__(
        self,
        embedding: EmbeddingService,
        sparse_embedding: SparseEmbeddingService,
        vector: VectorService,
    ):
        self._embedding = embedding
        self._sparse = sparse_embedding
        self._vector = vector

    async def retrieve(
        self,
        question: str,
        top_k: int,
        source_id: str | None = None,
        categories: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        # Embeddings denso y sparse en paralelo
        dense_vec, sparse_vec = await _gather(
            self._embedding.embed_query(question),
            self._sparse.embed_query(question),
        )
        filters: dict = {}
        if source_id is not None:
            filters["source_id"] = source_id
        if categories:
            filters["category"] = categories
        return self._vector.search(dense_vec, sparse_vec, top_k, filters or None)


async def _gather(coro_a, coro_b):
    """Ejecuta dos coroutines en paralelo y devuelve sus resultados."""
    import asyncio
    return await asyncio.gather(coro_a, coro_b)
