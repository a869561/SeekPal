from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from qdrant_client.http.models import SparseVector

from app.services.rag.index_service import IndexService


def _make_sparse(n: int = 1) -> list[SparseVector]:
    """Devuelve n SparseVectors de prueba."""
    return [SparseVector(indices=[0], values=[1.0])] * n


def _make_index_service(embedding=None, sparse_embedding=None, vector=None) -> IndexService:
    if embedding is None:
        embedding = MagicMock()
        embedding.embed_texts = AsyncMock(return_value=[[0.1] * 4])
    if sparse_embedding is None:
        sparse_embedding = MagicMock()
        sparse_embedding.embed_texts = AsyncMock(return_value=_make_sparse())
    if vector is None:
        vector = MagicMock()
        vector.upsert = MagicMock()
        vector.delete_by_file = MagicMock()
    return IndexService(
        embedding=embedding,
        sparse_embedding=sparse_embedding,
        vector=vector,
        chunk_size=512,
        overlap=64,
    )


async def test_index_file_done(tmp_text_file: Path):
    embedding = MagicMock()
    embedding.embed_texts = AsyncMock(return_value=[[0.1] * 4])

    sparse_embedding = MagicMock()
    sparse_embedding.embed_texts = AsyncMock(return_value=_make_sparse())

    vector = MagicMock()
    vector.upsert = MagicMock()
    vector.delete_by_file = MagicMock()

    svc = IndexService(
        embedding=embedding,
        sparse_embedding=sparse_embedding,
        vector=vector,
        chunk_size=512,
        overlap=64,
    )
    result = await svc.index_file(
        file_id="f1",
        source_id="s1",
        file_name=tmp_text_file.name,
        category="text",
        extension=".txt",
        path=tmp_text_file,
    )
    assert result.status == "done"
    assert result.chunks >= 1
    vector.delete_by_file.assert_called_once_with("f1")
    assert vector.upsert.called


async def test_index_unsupported_skipped(tmp_path: Path):
    f = tmp_path / "audio.mp3"
    # Bytes con valores nulos y altos: no pueden ser confundidos con texto UTF-8
    f.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd\xfc")
    svc = _make_index_service()
    result = await svc.index_file(
        file_id="f1",
        source_id="s1",
        file_name="audio.mp3",
        category="audio",
        extension=".mp3",
        path=f,
    )
    assert result.status == "skipped"
    assert result.chunks == 0


async def test_index_broken_pdf_failed(tmp_path: Path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"not a real pdf")
    svc = _make_index_service()
    result = await svc.index_file(
        file_id="f1",
        source_id="s1",
        file_name="broken.pdf",
        category="document",
        extension=".pdf",
        path=f,
    )
    assert result.status == "failed"
    assert result.error
