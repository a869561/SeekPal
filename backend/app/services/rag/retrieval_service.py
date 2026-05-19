from __future__ import annotations

from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_service import VectorService


class RetrievalService:
    def __init__(self, embedding: EmbeddingService, vector: VectorService):
        self._embedding = embedding
        self._vector = vector

    async def retrieve(
        self,
        question: str,
        top_k: int,
        source_id: str | None = None,
        categories: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        query_vector = await self._embedding.embed_query(question)
        filters: dict = {}
        if source_id is not None:
            filters["source_id"] = source_id
        if categories:
            filters["category"] = categories
        return self._vector.search(query_vector, top_k, filters or None)
