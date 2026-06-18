"""Tests del suelo RELATIVO de relevancia del reranker en
RetrievalService._rerank_and_mmr.

El suelo conserva los candidatos cuyo score quede como mucho a `keep_margin`
por debajo del mejor; descarta la cola más lejana. Es relativo (no absoluto)
para no colapsar en consultas cuyos logits caen en bloque (p.ej. cross-lingual).
"""
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


def _make_service(reranker, keep_margin):
    svc = object.__new__(RetrievalService)
    svc._embedding = None
    svc._sparse = None
    svc._vector = None
    svc._reranker = reranker
    svc._reranker_multiplier = 3
    svc._reranker_keep_margin = keep_margin
    svc._mmr_enabled = False
    svc._mmr_lambda = 0.7
    return svc


@pytest.mark.asyncio
async def test_drops_tail_beyond_margin():
    cands = [_chunk("a"), _chunk("b"), _chunk("c"), _chunk("d")]
    # top=1.2; margin=1.2 → corte en 0.0. a=1.2 b=0.1 pasan; c=-1.2 d=-1.8 fuera.
    svc = _make_service(_FakeReranker([1.2, 0.1, -1.2, -1.8]), keep_margin=1.2)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    assert [c.chunk_id for c in out] == ["a", "b"]


@pytest.mark.asyncio
async def test_keeps_cluster_when_all_low_but_close():
    # Caso 'fauna marina': todos los scores negativos pero juntos. Un suelo
    # absoluto los habría podado a 1; el relativo conserva el clúster completo.
    cands = [_chunk("a"), _chunk("b"), _chunk("c")]
    svc = _make_service(_FakeReranker([-1.06, -1.31, -1.60]), keep_margin=1.2)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    # top=-1.06; corte=-2.26 → entran los tres.
    assert [c.chunk_id for c in out] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_always_keeps_top():
    # Aunque la cola caiga lejos, el mejor siempre se conserva.
    cands = [_chunk("a"), _chunk("b"), _chunk("c")]
    svc = _make_service(_FakeReranker([-0.8, -3.0, -3.5]), keep_margin=1.2)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    assert [c.chunk_id for c in out] == ["a"]


@pytest.mark.asyncio
async def test_none_disables_threshold():
    cands = [_chunk("a"), _chunk("b"), _chunk("c")]
    svc = _make_service(_FakeReranker([1.0, -0.5, -2.0]), keep_margin=None)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=10)
    # Sin suelo → se mantienen todos, solo reordenados por score.
    assert [c.chunk_id for c in out] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_threshold_respects_top_k():
    cands = [_chunk(f"c{i}") for i in range(6)]
    svc = _make_service(_FakeReranker([2.0, 1.5, 1.0, 0.5, 0.2, 0.1]), keep_margin=1.2)
    out = await svc._rerank_and_mmr("q", [0.0], cands, top_k=3)
    # Todos dentro del margen (top=2.0, corte=0.8 → c0..c2), pero top_k=3 limita.
    assert len(out) == 3
    assert [c.chunk_id for c in out] == ["c0", "c1", "c2"]
