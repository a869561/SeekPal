"""Tests del algoritmo MMR (Maximum Marginal Relevance) en retrieval."""

from __future__ import annotations

from app.services.rag.retrieval_service import _cosine, _mmr_select
from app.services.rag.types import RetrievedChunk


def _chunk(chunk_id: str, file_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, file_id=file_id, source_id="s1", text="",
        page=None, offset_start=0, offset_end=0, file_name="x",
        category="text", extension=".txt", score=score,
    )


def test_cosine_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert _cosine(v, v) == 1.0


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine(a, b) == 0.0


def test_cosine_zero_vector_returns_zero():
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_mmr_returns_all_when_few_candidates():
    """Si hay <= top_k candidatos, devuelve todos sin reordenar."""
    chunks = [_chunk("c1", "f1", 0.9), _chunk("c2", "f1", 0.8)]
    vecs = [[1.0, 0.0], [0.0, 1.0]]
    result = _mmr_select(chunks, [1.0, 1.0], vecs, top_k=5, lambda_param=0.7)
    assert result == chunks


def test_mmr_first_pick_is_most_relevant():
    """El primer seleccionado siempre es el de mayor relevancia normalizada."""
    chunks = [_chunk("low", "f1", 0.1), _chunk("high", "f2", 0.9), _chunk("mid", "f3", 0.5)]
    vecs = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
    result = _mmr_select(chunks, [1.0, 0.0], vecs, top_k=1, lambda_param=1.0)
    assert result[0].chunk_id == "high"


def test_mmr_diversifies_when_lambda_low():
    """Con lambda=0 (solo diversidad), evita seleccionar chunks parecidos."""
    # Dos chunks identicos (vec) y uno ortogonal. MMR debe coger el ortogonal
    # como segundo aunque el segundo identico tenga score similar.
    chunks = [
        _chunk("a", "f1", 0.9),  # vec [1,0]
        _chunk("b", "f1", 0.8),  # vec [1,0] (identico al a)
        _chunk("c", "f2", 0.7),  # vec [0,1] (ortogonal)
    ]
    vecs = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    result = _mmr_select(chunks, [1.0, 0.5], vecs, top_k=2, lambda_param=0.0)
    ids = [c.chunk_id for c in result]
    # Primer pick puede ser cualquiera con max relevancia normalizada;
    # el segundo debe ser el ortogonal (c) no el duplicado.
    assert "c" in ids


def test_mmr_pure_relevance_when_lambda_one():
    """Con lambda=1 (solo relevancia), equivale a sort por score."""
    chunks = [
        _chunk("a", "f1", 0.9),
        _chunk("b", "f1", 0.8),
        _chunk("c", "f2", 0.95),
    ]
    vecs = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    result = _mmr_select(chunks, [1.0, 0.5], vecs, top_k=2, lambda_param=1.0)
    ids = [c.chunk_id for c in result]
    assert ids == ["c", "a"]


def test_mmr_handles_none_vectors():
    """Si algun chunk_vec es None (NaN fallback), no crashea."""
    chunks = [_chunk("a", "f1", 0.9), _chunk("b", "f2", 0.8)]
    vecs = [[1.0, 0.0], None]
    result = _mmr_select(chunks, [1.0, 0.0], vecs, top_k=2, lambda_param=0.7)
    assert len(result) == 2


def test_mmr_balanced_lambda_07_scores_cercanos():
    """Lambda=0.7 con scores cercanos (escenario tipico post-reranker):
    sin MMR top-3 = [f1-1, f1-2, f1-3]. Con MMR el chunk de f2 (similar score
    pero contenido distinto) entra en lugar del 3er chunk de f1 redundante."""
    chunks = [
        _chunk("f1-1", "f1", 0.95),  # mejor
        _chunk("f2-1", "f2", 0.91),  # segundo mejor, fichero distinto
        _chunk("f1-2", "f1", 0.85),
        _chunk("f1-3", "f1", 0.80),
        _chunk("f1-4", "f1", 0.75),
    ]
    # f1-* identicos entre si; f2-1 ortogonal
    vecs = [
        [1.0, 0.0],
        [0.0, 1.0],
        [1.0, 0.0],
        [1.0, 0.0],
        [1.0, 0.0],
    ]
    result = _mmr_select(chunks, [1.0, 0.5], vecs, top_k=3, lambda_param=0.7)
    file_ids = [c.file_id for c in result]
    assert file_ids == ["f1", "f2", "f1"], f"esperado [f1,f2,f1], obtuvo {file_ids}"


def test_mmr_respects_gap_when_lambda_high():
    """Si hay gap grande de relevancia, MMR=0.7 prioriza relevancia (correcto):
    no fuerza diversidad a costa de meter resultados malos."""
    chunks = [
        _chunk("f1-1", "f1", 0.95),
        _chunk("f1-2", "f1", 0.93),
        _chunk("f1-3", "f1", 0.91),
        _chunk("f2-1", "f2", 0.20),  # gap grande
    ]
    vecs = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    result = _mmr_select(chunks, [1.0, 0.5], vecs, top_k=3, lambda_param=0.7)
    # f2-1 NO entra porque su relevancia normalizada es 0 y la diversidad max
    # (0.3) no compensa la relevancia de f1-3 (0.7 * relevancia normalizada).
    file_ids = [c.file_id for c in result]
    assert file_ids == ["f1", "f1", "f1"]


def test_mmr_low_lambda_forces_diversity_despite_gap():
    """Con lambda=0.2 (mucha diversidad), f2 entra aunque tenga score mucho menor."""
    chunks = [
        _chunk("f1-1", "f1", 0.95),
        _chunk("f1-2", "f1", 0.93),
        _chunk("f1-3", "f1", 0.91),
        _chunk("f2-1", "f2", 0.20),
    ]
    vecs = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
    result = _mmr_select(chunks, [1.0, 0.5], vecs, top_k=3, lambda_param=0.2)
    file_ids = {c.file_id for c in result}
    assert "f2" in file_ids
