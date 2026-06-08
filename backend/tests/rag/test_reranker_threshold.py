"""Tests del suelo de relevancia del reranker en RetrievalService._rerank_and_mmr."""
from __future__ import annotations

import pytest

from app.services.rag.retrieval_service import RetrievalService
from app.services.rag.types import RetrievedChunk


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, file_id="f1", source_id="s1", text=f"texto {chunk_id}",
        page=None, offset_start=0, offset_end=10, file_name="x.txt",
        category="text", extension=".txt", score=0.0,
    )


class _FakeReranker:
    """Asigna a cada passage el score de la misma posición en `scores`."""
    def __init__(self, scores: list[float]):
        self._scores = scores

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        return self._scores[: len(passages)]


def _make_service(reranker, min_score):
    svc = object.__new__(RetrievalService)
    svc._embedding = None
    svc._sparse = None
    svc._vector = None
    svc._reranker = reranker
    svc._reranker_multiplier = 3
    svc._reranker_min_score = min_score
    svc._mmr_enabled = False
    svc._mmr_lambda = 0.7
    return svc


@pytest.mark.asyncio
async def test_drops_below_threshold():
    cands = [_chunk("a"), _chunk("b"), _chunk("c"), _chunk("d")]
    # a=1.2 b=0.1 (relevantes >=0) ; c=-1.2 d=-1.8 (basura)
    svc = _make_service(_FakeReranker([1.2, 0.1, -1.2, -1.8]), min_score=0.0)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    assert [c.chunk_id for c in out] == ["a", "b"]


@pytest.mark.asyncio
async def test_keeps_at_least_one_when_all_below():
    cands = [_chunk("a"), _chunk("b"), _chunk("c")]
    svc = _make_service(_FakeReranker([-0.8, -1.2, -1.5]), min_score=0.0)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    # Todos por debajo del umbral → conserva el mejor (score más alto = -0.8)
    assert [c.chunk_id for c in out] == ["a"]


@pytest.mark.asyncio
async def test_none_disables_threshold():
    cands = [_chunk("a"), _chunk("b"), _chunk("c")]
    svc = _make_service(_FakeReranker([1.0, -0.5, -2.0]), min_score=None)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    # Sin umbral → se mantienen todos, solo reordenados por score
    assert [c.chunk_id for c in out] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_threshold_respects_top_k():
    cands = [_chunk(f"c{i}") for i in range(6)]
    svc = _make_service(_FakeReranker([2.0, 1.5, 1.0, 0.5, 0.2, 0.1]), min_score=0.0)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=3)
    # Todos pasan el umbral, pero top_k=3 limita el resultado final
    assert len(out) == 3
    assert [c.chunk_id for c in out] == ["c0", "c1", "c2"]
