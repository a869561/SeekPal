from pathlib import Path

from app.services.rag.extractors.text import TextExtractor


def test_extracts_plain_text(tmp_text_file: Path):
    extractor = TextExtractor()
    doc = extractor.extract(tmp_text_file)
    assert "SeekPal" in doc.text
    assert doc.extractor == "text"
    assert doc.page_map == []


def test_extracts_markdown(tmp_md_file: Path):
    extractor = TextExtractor()
    doc = extractor.extract(tmp_md_file)
    assert "Título" in doc.text
    assert doc.extractor == "text"


def test_handles_encoding_errors(tmp_path: Path):
    p = tmp_path / "bad_encoding.txt"
    p.write_bytes(b"Hello \xff world")
    extractor = TextExtractor()
    doc = extractor.extract(p)
    assert "Hello" in doc.text


def test_supported_extensions():
    ext = TextExtractor()
    assert ".txt" in ext.supported_extensions()
    assert ".md" in ext.supported_extensions()
