from __future__ import annotations

import asyncio

from app.services.rag.embedding_service import (
    EmbeddingService,
    RerankerService,
    SparseEmbeddingService,
)
from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_service import VectorService


class RetrievalService:
    """Recupera chunks combinando hybrid search (dense + sparse) con reranking opcional.

    Si hay reranker activo:
      1. Vector search devuelve `top_k * multiplier` candidatos (sobre-recupera).
      2. Reranker reordena con cross-encoder mas preciso.
      3. Devolvemos los top_k mejores tras el rerank.

    Sin reranker, vector search devuelve directamente top_k.
    """

    def __init__(
        self,
        embedding: EmbeddingService,
        sparse_embedding: SparseEmbeddingService,
        vector: VectorService,
        reranker: RerankerService | None = None,
        reranker_multiplier: int = 3,
    ):
        self._embedding = embedding
        self._sparse = sparse_embedding
        self._vector = vector
        self._reranker = reranker
        self._reranker_multiplier = max(1, reranker_multiplier)

    async def retrieve(
        self,
        question: str,
        top_k: int,
        source_id: str | None = None,
        categories: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        # Sobre-recuperar si hay reranker para darle margen al cross-encoder
        candidate_k = top_k * self._reranker_multiplier if self._reranker else top_k

        # Embeddings denso y sparse en paralelo
        dense_vec, sparse_vec = await asyncio.gather(
            self._embedding.embed_query(question),
            self._sparse.embed_query(question),
        )
        filters: dict = {}
        if source_id is not None:
            filters["source_id"] = source_id
        if categories:
            filters["category"] = categories

        candidates = await asyncio.to_thread(
            self._vector.search, dense_vec, sparse_vec, candidate_k, filters or None
        )

        if not self._reranker or len(candidates) <= 1:
            return candidates[:top_k]

        # Cross-encoder rerank: scores frescos sobre (query, passage)
        passages = [c.text for c in candidates]
        try:
            scores = await self._reranker.rerank(question, passages)
        except Exception as exc:  # noqa: BLE001
            print(f"[seekpal] Reranker fallo, usando scores hybrid: {exc}")
            return candidates[:top_k]

        # Reasignar score y reordenar
        scored = list(zip(candidates, scores, strict=False))
        scored.sort(key=lambda x: x[1], reverse=True)
        result: list[RetrievedChunk] = []
        for chunk, new_score in scored[:top_k]:
            chunk.score = float(new_score)
            result.append(chunk)
        return result
