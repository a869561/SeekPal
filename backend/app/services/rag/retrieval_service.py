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


def _rrf_fuse(
    rankings: list[list[RetrievedChunk]],
    k: int = 60,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion sobre N rankings de chunks.

    score_rrf(c) = sum(1 / (k + rank_i(c))) para cada ranking donde c aparece.
    k=60 es el valor estandar del paper original (Cormack et al. 2009).

    Devuelve los chunks unicos (por chunk_id) ordenados por score RRF descendente.
    El score original del chunk se reemplaza por el score RRF."""
    if not rankings:
        return []
    if len(rankings) == 1:
        return rankings[0]

    accumulator: dict[str, tuple[RetrievedChunk, float]] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            contribution = 1.0 / (k + rank + 1)
            if chunk.chunk_id in accumulator:
                existing_chunk, existing_score = accumulator[chunk.chunk_id]
                accumulator[chunk.chunk_id] = (existing_chunk, existing_score + contribution)
            else:
                accumulator[chunk.chunk_id] = (chunk, contribution)

    fused = []
    for chunk, score in accumulator.values():
        chunk.score = score
        fused.append(chunk)
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


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

    Flujo single-query (retrieve):
      1. Embed query (dense + sparse) en paralelo.
      2. Hybrid search Qdrant con RRF (recupera top_k * multiplier candidatos).
      3. Reranker cross-encoder (opcional) reordena con mayor precision.
      4. MMR (opcional) diversifica el top_k final.

    Flujo multi-query (retrieve_multi):
      Como el anterior, pero repite los pasos 1-2 para cada variante de la
      pregunta en paralelo, RRF-funde todos los rankings en uno y aplica
      reranker + MMR una sola vez sobre el conjunto unificado.
    """

    def __init__(
        self,
        embedding: EmbeddingService,
        sparse_embedding: SparseEmbeddingService,
        vector: VectorService,
        reranker: RerankerService | None = None,
        reranker_multiplier: int = 3,
        reranker_min_score: float | None = None,
        mmr_enabled: bool = True,
        mmr_lambda: float = 0.7,
    ):
        self._embedding = embedding
        self._sparse = sparse_embedding
        self._vector = vector
        self._reranker = reranker
        self._reranker_multiplier = max(1, reranker_multiplier)
        self._reranker_min_score = reranker_min_score
        self._mmr_enabled = mmr_enabled
        self._mmr_lambda = max(0.0, min(1.0, mmr_lambda))

    def _build_filters(
        self,
        source_id: str | None,
        categories: list[str] | None,
    ) -> dict:
        filters: dict = {}
        if source_id is not None:
            filters["source_id"] = source_id
        if categories:
            filters["category"] = categories
        return filters

    async def _rerank_and_mmr(
        self,
        question: str,
        dense_vec: list[float],
        candidates: list[RetrievedChunk],
        top_k: int,
        use_mmr: bool = True,
    ) -> list[RetrievedChunk]:
        """Aplica reranker (si disponible) y MMR sobre una lista de candidatos.
        Usado tanto por retrieve() como por retrieve_multi()."""
        if len(candidates) <= 1:
            return candidates[:top_k]

        # Rerank con cross-encoder si esta disponible
        if self._reranker:
            passages = [c.embed_text for c in candidates]
            try:
                scores = await self._reranker.rerank(question, passages)
                for chunk, new_score in zip(candidates, scores, strict=False):
                    chunk.score = float(new_score)
                candidates.sort(key=lambda c: c.score, reverse=True)

                # Suelo de relevancia: descarta la cola irrelevante (scores del
                # reranker comparables entre si). Conserva siempre >=1 para no
                # devolver vacio cuando hay un mejor candidato aunque sea debil.
                if self._reranker_min_score is not None:
                    kept = [c for c in candidates if c.score >= self._reranker_min_score]
                    candidates = kept if kept else candidates[:1]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Reranker fallo, usando scores hybrid: %s", exc)

        # MMR: diversifica top_k para evitar que sean todos del mismo fichero.
        # use_mmr=False permite saltarlo en paths donde no aporta (búsqueda de
        # ficheros, que ya agrupa por fichero): re-embeber todos los candidatos
        # en cada query cuesta decenas de segundos en GPUs modestas.
        if self._mmr_enabled and use_mmr and len(candidates) > top_k:
            # Reembebemos los textos de los candidatos para tener vectores
            # densos comparables con la query. Los vectores originales de
            # Qdrant no se devuelven en query_points (solo el payload).
            try:
                chunk_vecs = await self._embedding.embed_texts(
                    [c.text for c in candidates]
                )
                return _mmr_select(candidates, dense_vec, chunk_vecs, top_k, self._mmr_lambda)
            except Exception as exc:  # noqa: BLE001
                logger.warning("MMR fallo, usando orden por score: %s", exc)

        return candidates[:top_k]

    async def retrieve(
        self,
        question: str,
        top_k: int,
        source_id: str | None = None,
        categories: list[str] | None = None,
        use_mmr: bool = True,
    ) -> list[RetrievedChunk]:
        # Sobre-recuperar para dar margen a reranker y/o MMR.
        candidate_k = top_k * self._reranker_multiplier if (self._reranker or self._mmr_enabled) else top_k

        # Embeddings denso y sparse en paralelo
        dense_vec, sparse_vec = await asyncio.gather(
            self._embedding.embed_query(question),
            self._sparse.embed_query(question),
        )
        filters = self._build_filters(source_id, categories)

        candidates = await asyncio.to_thread(
            self._vector.search, dense_vec, sparse_vec, candidate_k, filters or None
        )

        return await self._rerank_and_mmr(question, dense_vec, candidates, top_k, use_mmr)

    async def retrieve_multi(
        self,
        questions: list[str],
        top_k: int,
        source_id: str | None = None,
        categories: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Multi-query retrieval: recupera candidatos para cada formulacion de la
        pregunta en paralelo y los fusiona con RRF antes de reranking y MMR.

        Mejora el recall cubriendo sinonimos y angulos distintos del mismo tema.
        El reranker y MMR se aplican una sola vez sobre el conjunto unificado,
        usando siempre la pregunta ORIGINAL (questions[0]) como referencia.
        """
        if not questions:
            return []
        if len(questions) == 1:
            return await self.retrieve(questions[0], top_k, source_id, categories)

        candidate_k = top_k * self._reranker_multiplier
        filters = self._build_filters(source_id, categories)

        # Embeddings denso+sparse para todas las queries en paralelo
        query_vecs: list[tuple[list[float], object]] = list(
            await asyncio.gather(
                *[
                    asyncio.gather(
                        self._embedding.embed_query(q),
                        self._sparse.embed_query(q),
                    )
                    for q in questions
                ]
            )
        )

        # Busqueda Qdrant para cada query en paralelo
        per_query_results: list[list[RetrievedChunk]] = list(
            await asyncio.gather(
                *[
                    asyncio.to_thread(
                        self._vector.search,
                        dense_vec, sparse_vec, candidate_k, filters or None,
                    )
                    for dense_vec, sparse_vec in query_vecs
                ]
            )
        )

        # RRF-funde todos los rankings en uno unico
        candidates = _rrf_fuse(per_query_results)

        # Reranker y MMR usando la pregunta ORIGINAL (questions[0])
        original_dense = query_vecs[0][0]
        return await self._rerank_and_mmr(questions[0], original_dense, candidates, top_k)
