"""Tests para el framework de benchmarking RAG (benchmark_service).

Cubre las metricas puras (recall@k, MRR, percentil) sin conexion a Qdrant
ni modelos reales, y el runner score_pipeline con un retrieval mock.
"""

from __future__ import annotations

import pytest

from app.services.rag.benchmark_service import (
    BenchDataset,
    BenchQuery,
    BenchReport,
    score_pipeline,
    mean_reciprocal_rank,
    percentile,
    recall_at_k,
    reciprocal_rank,
)
from app.services.rag.types import RetrievedChunk


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, file_id="f1", source_id="s1",
        text=f"texto {chunk_id}", page=None,
        offset_start=0, offset_end=10,
        file_name="x.txt", category="text", extension=".txt", score=0.9,
    )


class _MockRetrieval:
    def __init__(self, results: dict[str, list[str]]):
        self._results = results

    async def retrieve(self, question: str, top_k: int, **kwargs) -> list[RetrievedChunk]:
        ids = self._results.get(question, [])[:top_k]
        return [_chunk(cid) for cid in ids]


# --------------------------------------------------------------------------
# recall_at_k
# --------------------------------------------------------------------------

def test_recall_perfect():
    assert recall_at_k(["a", "b", "c"], {"a", "b", "c"}) == 1.0

def test_recall_zero():
    assert recall_at_k(["x", "y"], {"a", "b"}) == 0.0

def test_recall_partial():
    r = recall_at_k(["a", "x", "b"], {"a", "b", "c"})
    assert abs(r - 2/3) < 1e-9

def test_recall_empty_relevant():
    assert recall_at_k(["a", "b"], set()) == 1.0

def test_recall_empty_retrieved():
    assert recall_at_k([], {"a", "b"}) == 0.0


# --------------------------------------------------------------------------
# reciprocal_rank
# --------------------------------------------------------------------------

def test_rr_first_hit():
    assert reciprocal_rank(["a", "b", "c"], {"a"}) == 1.0

def test_rr_second_hit():
    assert reciprocal_rank(["x", "a", "c"], {"a"}) == 0.5

def test_rr_third_hit():
    assert abs(reciprocal_rank(["x", "y", "a"], {"a"}) - 1/3) < 1e-9

def test_rr_no_hit():
    assert reciprocal_rank(["x", "y"], {"a", "b"}) == 0.0

def test_rr_empty_retrieved():
    assert reciprocal_rank([], {"a"}) == 0.0


# --------------------------------------------------------------------------
# mean_reciprocal_rank
# --------------------------------------------------------------------------

def test_mrr_basic():
    rrs = [1.0, 0.5, 0.25]
    expected = (1.0 + 0.5 + 0.25) / 3
    assert abs(mean_reciprocal_rank(rrs) - expected) < 1e-9

def test_mrr_empty():
    assert mean_reciprocal_rank([]) == 0.0

def test_mrr_all_zeros():
    assert mean_reciprocal_rank([0.0, 0.0, 0.0]) == 0.0


# --------------------------------------------------------------------------
# percentile
# --------------------------------------------------------------------------

def test_percentile_median():
    assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0

def test_percentile_min_max():
    values = [10.0, 20.0, 30.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 100) == 30.0

def test_percentile_interpolation():
    assert abs(percentile([0.0, 100.0], 50) - 50.0) < 1e-9

def test_percentile_empty():
    assert percentile([], 95) == 0.0

def test_percentile_single():
    assert percentile([42.0], 99) == 42.0


# --------------------------------------------------------------------------
# BenchDataset
# --------------------------------------------------------------------------

def test_dataset_from_list():
    ds = BenchDataset.from_list([
        {"question": "q1", "relevant_ids": ["a", "b"]},
        {"question": "q2", "relevant_ids": ["c"]},
    ])
    assert len(ds) == 2
    assert ds.queries[0].question == "q1"
    assert ds.queries[1].relevant_ids == ["c"]

def test_dataset_from_list_with_metadata():
    ds = BenchDataset.from_list([
        {"question": "q", "relevant_ids": ["a"], "metadata": {"source": "test"}},
    ])
    assert ds.queries[0].metadata == {"source": "test"}

def test_dataset_json_roundtrip(tmp_path):
    ds = BenchDataset.from_list([
        {"question": "Que es Python?", "relevant_ids": ["py::0", "py::1"]},
    ])
    path = tmp_path / "dataset.json"
    ds.to_json(path)
    ds2 = BenchDataset.from_json(path)
    assert len(ds2) == 1
    assert ds2.queries[0].question == "Que es Python?"
    assert ds2.queries[0].relevant_ids == ["py::0", "py::1"]


# --------------------------------------------------------------------------
# score_pipeline
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_perfect_retrieval():
    ds = BenchDataset.from_list([{"question": "q1", "relevant_ids": ["a", "b"]}])
    mock = _MockRetrieval({"q1": ["a", "b", "c"]})
    report = await score_pipeline(ds, mock, top_k=5)
    assert report.mean_recall == 1.0
    assert report.mrr == 1.0
    assert report.num_queries == 1
    assert report.top_k == 5

@pytest.mark.asyncio
async def test_score_no_retrieval():
    ds = BenchDataset.from_list([{"question": "q1", "relevant_ids": ["a"]}])
    mock = _MockRetrieval({"q1": []})
    report = await score_pipeline(ds, mock, top_k=5)
    assert report.mean_recall == 0.0
    assert report.mrr == 0.0

@pytest.mark.asyncio
async def test_score_partial_retrieval():
    ds = BenchDataset.from_list([{"question": "q1", "relevant_ids": ["a", "b"]}])
    mock = _MockRetrieval({"q1": ["a", "x", "y"]})
    report = await score_pipeline(ds, mock, top_k=5)
    assert abs(report.mean_recall - 0.5) < 1e-9
    assert report.mrr == 1.0

@pytest.mark.asyncio
async def test_score_multiple_queries():
    ds = BenchDataset.from_list([
        {"question": "q1", "relevant_ids": ["a"]},
        {"question": "q2", "relevant_ids": ["b"]},
    ])
    mock = _MockRetrieval({"q1": ["a", "x"], "q2": ["x", "b"]})
    report = await score_pipeline(ds, mock, top_k=5)
    assert report.num_queries == 2
    assert abs(report.mean_recall - 1.0) < 1e-9
    assert abs(report.mrr - 0.75) < 1e-9

@pytest.mark.asyncio
async def test_score_latency_recorded():
    ds = BenchDataset.from_list([{"question": "q1", "relevant_ids": ["a"]}])
    mock = _MockRetrieval({"q1": ["a"]})
    report = await score_pipeline(ds, mock, top_k=5)
    assert report.latency_p50_ms >= 0
    assert report.per_query[0].latency_ms >= 0

@pytest.mark.asyncio
async def test_score_summary_readable():
    ds = BenchDataset.from_list([{"question": "q1", "relevant_ids": ["a"]}])
    mock = _MockRetrieval({"q1": ["a"]})
    report = await score_pipeline(ds, mock, top_k=10)
    summary = report.summary()
    assert "Recall@10" in summary
    assert "MRR" in summary
    assert "Latency" in summary

@pytest.mark.asyncio
async def test_score_to_dict_complete():
    ds = BenchDataset.from_list([{"question": "q1", "relevant_ids": ["a"]}])
    mock = _MockRetrieval({"q1": ["a"]})
    report = await score_pipeline(ds, mock, top_k=5)
    d = report.to_dict()
    assert "mean_recall" in d
    assert "mrr" in d
    assert "per_query" in d
    assert isinstance(d["per_query"], list)
    assert d["per_query"][0]["question"] == "q1"
