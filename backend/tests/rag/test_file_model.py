from datetime import datetime

from app.models.file import FileMetadata, RagMetadata


def test_file_metadata_accepts_rag_block():
    meta = FileMetadata(
        wordCount=10,
        rag=RagMetadata(
            indexStatus="done",
            indexedChunks=3,
            lastIndexedAt=datetime(2026, 5, 18),
            extractor="pdf",
        ),
    )
    assert meta.rag.indexStatus == "done"
    assert meta.rag.indexedChunks == 3


def test_rag_metadata_optional():
    meta = FileMetadata()
    assert meta.rag is None


def test_rag_metadata_defaults():
    rag = RagMetadata()
    assert rag.indexStatus == "pending"
    assert rag.indexedChunks == 0
    assert rag.lastIndexedAt is None
    assert rag.error is None
