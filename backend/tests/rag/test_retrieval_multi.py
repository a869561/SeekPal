"""Tests para RetrievalService.retrieve_multi (multi-query retrieval).

Usa mocks ligeros — no carga modelos ni Qdrant reales — para validar
la lógica de expansión+fusión RRF sin dependencias externas.
"""

from __future__ import annotations

import pytest

from app.services.rag.retrieval_service import RetrievalService, _rrf_fuse
from app.services.rag.types import RetrievedChunk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(chunk_id: str, file_id: str = "f1", score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, file_id=file_id, source_id="s1", text=f"texto {chunk_id}",
        page=None, offset_start=0, offset_end=10, file_name="x.txt",
        category="text", extension=".txt", score=score,
    )


class _FakeEmbedding:
    """Devuelve vectores fijos de 4D sin cargar ningún modelo."""
    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        return [[1.0, 0.0, 0.0, 0.0]] * len(texts)


class _FakeSparse:
    """Devuelve SparseVector vacío (compatible con VectorService.search mock)."""
    async def embed_query(self, text: str):
        from qdrant_client.http.models import SparseVector
        return SparseVector(indices=[], values=[])


class _FakeVector:
    """Devuelve listas de chunks fijas según la query (para simular distintos resultados)."""
    def __init__(self, results_by_call: list[list[RetrievedChunk]]):
        self._results = results_by_call
        self._call_count = 0

    def search(self, dense_vec, sparse_vec, top_k, filters) -> list[RetrievedChunk]:
        idx = min(self._call_count, len(self._results) - 1)
        self._call_count += 1
        return self._results[idx]


def _make_service(results_by_call: list[list[RetrievedChunk]]) -> RetrievalService:
    svc = object.__new__(RetrievalService)
    svc._embedding = _FakeEmbedding()
    svc._sparse = _FakeSparse()
    svc._vector = _FakeVector(results_by_call)
    svc._reranker = None
    svc._reranker_multiplier = 3
    svc._mmr_enabled = False  # desactivar MMR para tests simples
    svc._mmr_lambda = 0.7
    return svc


# ---------------------------------------------------------------------------
# Tests para _rrf_fuse (la función auxiliar usada por retrieve_multi)
# ---------------------------------------------------------------------------

def test_rrf_fuse_empty():
    assert _rrf_fuse([]) == []


def test_rrf_fuse_single_ranking():
    chunks = [_chunk("a", score=0.9), _chunk("b", score=0.7)]
    result = _rrf_fuse([chunks])
    assert [c.chunk_id for c in result] == ["a", "b"]


def test_rrf_fuse_deduplicates_across_rankings():
    r1 = [_chunk("a", score=0.9), _chunk("b", score=0.8)]
    r2 = [_chunk("a", score=0.7), _chunk("c", score=0.6)]
    result = _rrf_fuse([r1, r2])
    ids = [c.chunk_id for c in result]
    # "a" aparece en ambos rankings → score RRF más alto
    assert ids[0] == "a"
    assert len(ids) == 3  # a, b, c — sin duplicados


def test_rrf_fuse_score_formula():
    """El score RRF de rank 0 en dos rankings separados es 2/(60+1) ≈ 0.0328.
    (Con un solo ranking _rrf_fuse devuelve la lista original sin re-puntuar.)
    """
    # Para activar el cálculo RRF necesitamos al menos 2 rankings
    r1 = [_chunk("x", score=1.0)]
    r2 = [_chunk("x", score=0.5)]  # mismo chunk, ranking 2
    result = _rrf_fuse([r1, r2])
    # rank=0 en ambos → 1/(60+1) + 1/(60+1) = 2/61
    expected = 2.0 / (60 + 0 + 1)
    assert abs(result[0].score - expected) < 1e-9


def test_rrf_fuse_two_rankings_combine_scores():
    """Un chunk que aparece en posicion 0 de dos rankings debe tener score ≈ 2/(60+1)."""
    chunk_a = _chunk("a", score=0.9)
    r1 = [chunk_a]
    r2 = [_chunk("a", score=0.5)]  # mismo chunk_id
    result = _rrf_fuse([r1, r2])
    expected = 2.0 / (60 + 0 + 1)
    assert abs(result[0].score - expected) < 1e-9


# ---------------------------------------------------------------------------
# Tests para retrieve_multi
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_multi_empty_questions():
    svc = _make_service([])
    result = await svc.retrieve_multi([], top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_retrieve_multi_single_question_delegates_to_retrieve():
    """Con una sola pregunta, debe delegar a retrieve() (mismo comportamiento)."""
    chunks = [_chunk("a"), _chunk("b"), _chunk("c")]
    svc = _make_service([chunks])
    result = await svc.retrieve_multi(["pregunta"], top_k=2)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_retrieve_multi_fuses_results_from_multiple_queries():
    """Con 2 queries, recupera chunks de cada una y los fusiona por RRF."""
    r1 = [_chunk("a", score=0.9), _chunk("b", score=0.8)]
    r2 = [_chunk("c", score=0.7), _chunk("a", score=0.6)]  # "a" también aparece aquí

    svc = _make_service([r1, r2])
    result = await svc.retrieve_multi(["q1", "q2"], top_k=3)

    ids = [c.chunk_id for c in result]
    # "a" aparece en ambas queries → mayor score RRF → primer lugar
    assert ids[0] == "a"
    # Todos los chunks únicos están presentes
    assert set(ids) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_retrieve_multi_respects_top_k():
    """El resultado final no excede top_k aunque haya más candidatos fusionados."""
    r1 = [_chunk(f"q1_{i}", score=0.9 - i * 0.1) for i in range(5)]
    r2 = [_chunk(f"q2_{i}", score=0.9 - i * 0.1) for i in range(5)]
    svc = _make_service([r1, r2])
    result = await svc.retrieve_multi(["q1", "q2"], top_k=4)
    assert len(result) == 4


@pytest.mark.asyncio
async def test_retrieve_multi_no_duplicates_in_output():
    """Los chunks compartidos entre queries no aparecen duplicados en el resultado."""
    shared = _chunk("shared", score=0.9)
    r1 = [shared, _chunk("only1", score=0.8)]
    r2 = [_chunk("shared", score=0.7), _chunk("only2", score=0.6)]  # mismo chunk_id

    svc = _make_service([r1, r2])
    result = await svc.retrieve_multi(["q1", "q2"], top_k=10)

    ids = [c.chunk_id for c in result]
    assert ids.count("shared") == 1  # sin duplicados
