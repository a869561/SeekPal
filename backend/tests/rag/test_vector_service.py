import pytest

from app.services.rag.types import RetrievedChunk
from app.services.rag.vector_service import VectorService


@pytest.fixture
def vec_service():
    svc = VectorService(path=":memory:", collection="seekpal_test", dim=4)
    svc.ensure_collection()
    yield svc
    svc.close()


def _payload(**overrides):
    base = {
        "chunk_id": "f1::0",
        "file_id": "f1",
        "source_id": "s1",
        "text": "hola",
        "page": None,
        "offset_start": 0,
        "offset_end": 4,
        "category": "text",
        "extension": ".txt",
        "file_name": "x.txt",
    }
    base.update(overrides)
    return base


def test_upsert_and_search(vec_service):
    points = [
        ("f1::0", [1.0, 0.0, 0.0, 0.0], _payload(chunk_id="f1::0", text="vec uno")),
        ("f1::1", [0.0, 1.0, 0.0, 0.0], _payload(chunk_id="f1::1", text="vec dos")),
    ]
    vec_service.upsert(points)
    hits = vec_service.search([1.0, 0.0, 0.0, 0.0], top_k=2)
    assert len(hits) == 2
    assert hits[0].chunk_id == "f1::0"
    assert hits[0].score > hits[1].score


def test_delete_by_file_id(vec_service):
    vec_service.upsert([
        ("f1::0", [1.0, 0, 0, 0], _payload(file_id="f1")),
        ("f2::0", [0, 1.0, 0, 0], _payload(chunk_id="f2::0", file_id="f2")),
    ])
    vec_service.delete_by_file("f1")
    hits = vec_service.search([1.0, 0, 0, 0], top_k=10)
    file_ids = {h.file_id for h in hits}
    assert "f1" not in file_ids
    assert "f2" in file_ids


def test_delete_by_source_id(vec_service):
    vec_service.upsert([
        ("f1::0", [1.0, 0, 0, 0], _payload(source_id="s1")),
        ("f2::0", [0, 1.0, 0, 0], _payload(chunk_id="f2::0", source_id="s2")),
    ])
    vec_service.delete_by_source("s1")
    hits = vec_service.search([0, 1.0, 0, 0], top_k=10)
    assert all(h.source_id == "s2" for h in hits)


def test_count(vec_service):
    vec_service.upsert([
        ("f1::0", [1.0, 0, 0, 0], _payload()),
        ("f1::1", [0, 1.0, 0, 0], _payload(chunk_id="f1::1")),
    ])
    assert vec_service.count() == 2


def test_ensure_collection_idempotent(vec_service):
    vec_service.upsert([("f1::0", [1.0, 0, 0, 0], _payload())])
    vec_service.ensure_collection()  # segunda llamada no borra datos
    assert vec_service.count() == 1


def test_search_with_filter(vec_service):
    vec_service.upsert([
        ("f1::0", [1.0, 0, 0, 0], _payload(file_id="f1")),
        ("f2::0", [1.0, 0, 0, 0], _payload(chunk_id="f2::0", file_id="f2")),
    ])
    hits = vec_service.search([1.0, 0, 0, 0], top_k=10, filters={"file_id": "f1"})
    assert all(h.file_id == "f1" for h in hits)
    assert len(hits) == 1
