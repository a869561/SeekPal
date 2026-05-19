from pathlib import Path

from app.services.rag.extractors.docx import DocxExtractor


def test_extracts_text_from_docx(tmp_docx_file: Path):
    extractor = DocxExtractor()
    doc = extractor.extract(tmp_docx_file)
    assert "SeekPal" in doc.text
    assert doc.extractor == "docx"
    assert doc.page_map == []


def test_supported_extensions():
    ext = DocxExtractor()
    assert ".docx" in ext.supported_extensions()
