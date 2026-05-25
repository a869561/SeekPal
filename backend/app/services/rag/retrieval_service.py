from __future__ import annotations

import asyncio
import logging
import math

from app.services.rag.embedding_service import (
    EmbeddingService,
    RerankerService,
    SparseEmbeddingService,
)
from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_service import VectorService

logger = logging.getLogger("seekpal.retrieval")


def _cosine(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores. Asumimos misma dimension."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _mmr_select(
    candidates: list[RetrievedChunk],
    query_vec: list[float],
    chunk_vecs: list[list[float] | None],
    top_k: int,
    lambda_param: float,
) -> list[RetrievedChunk]:
    """Maximum Marginal Relevance: equilibra relevancia y diversidad.

    score(c) = lambda * sim(c, q) - (1-lambda) * max(sim(c, c') for c' ya elegido)

    lambda=1 -> solo relevancia (= comportamiento por defecto).
    lambda=0 -> solo diversidad (= maxima dispersion, ignora relevancia).
    lambda=0.7 (default) -> 70% relevancia, 30% diversidad. Balanceado para
    evitar que los top-k sean todos del mismo fichero sin perder calidad.
    """
    if not candidates or len(candidates) <= top_k:
        return candidates

    # Relevancia inicial: usamos el score que ya trae cada candidato.
    # Esos scores estan en escalas distintas (RRF, cosine, reranker)
    # asi que los normalizamos a [0, 1] para combinarlos con sim coseno.
    scores = [c.score for c in candidates]
    smin, smax = min(scores), max(scores)
    span = (smax - smin) or 1.0
    relevance = [(s - smin) / span for s in scores]

    selected_idx: list[int] = []
    remaining = set(range(len(candidates)))

    while remaining and len(selected_idx) < top_k:
        best_i: int | None = None
        best_score = -float("inf")
        for i in remaining:
            rel = relevance[i]
            if not selected_idx:
                mmr = rel  # primer pick = el mas relevante
            else:
                # diversidad: max similitud con los ya elegidos
                vec_i = chunk_vecs[i]
                if vec_i is None:
                    diversity_penalty = 0.0
                else:
                    sims = [
                        _cosine(vec_i, chunk_vecs[j])
                        for j in selected_idx
                        if chunk_vecs[j] is not None
                    ]
                    diversity_penalty = max(sims) if sims else 0.0
                mmr = lambda_param * rel - (1 - lambda_param) * diversity_penalty
            if mmr > best_score:
                best_score = mmr
                best_i = i
        if best_i is None:
            break
        selected_idx.append(best_i)
        remaining.discard(best_i)

    return [candidates[i] for i in selected_idx]


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
        mmr_enabled: bool = True,
        mmr_lambda: float = 0.7,
    ):
        self._embedding = embedding
        self._sparse = sparse_embedding
        self._vector = vector
        self._reranker = reranker
        self._reranker_multiplier = max(1, reranker_multiplier)
        self._mmr_enabled = mmr_enabled
        self._mmr_lambda = max(0.0, min(1.0, mmr_lambda))

    async def retrieve(
        self,
        question: str,
        top_k: int,
        source_id: str | None = None,
        categories: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        # Sobre-recuperar para dar margen a reranker y/o MMR. Si ambos estan
        # activos prevalece el multiplier del reranker (mas grande).
        if self._reranker or self._mmr_enabled:
            candidate_k = top_k * self._reranker_multiplier
        else:
            candidate_k = top_k

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

        if len(candidates) <= 1:
            return candidates[:top_k]

        # Rerank con cross-encoder si esta disponible
        if self._reranker:
            passages = [c.text for c in candidates]
            try:
                scores = await self._reranker.rerank(question, passages)
                for chunk, new_score in zip(candidates, scores, strict=False):
                    chunk.score = float(new_score)
                candidates.sort(key=lambda c: c.score, reverse=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reranker fallo, usando scores hybrid: %s", exc)

        # MMR: diversifica top_k para evitar que sean todos del mismo fichero
        if self._mmr_enabled and len(candidates) > top_k:
            # Reembebemos los textos de los candidatos para tener vectores
            # densos comparables con la query. Los vectores originales de
            # Qdrant no se devuelven en query_points (solo el payload).
            try:
                chunk_vecs = await self._embedding.embed_texts(
                    [c.text for c in candidates]
                )
                return _mmr_select(
                    candidates, dense_vec, chunk_vecs, top_k, self._mmr_lambda
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("MMR fallo, usando orden por score: %s", exc)

        return candidates[:top_k]
