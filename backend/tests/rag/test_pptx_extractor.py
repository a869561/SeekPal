from pathlib import Path

from app.services.rag.extractors.pptx import PptxExtractor


def test_extracts_text_from_pptx(tmp_pptx_file: Path):
    extractor = PptxExtractor()
    doc = extractor.extract(tmp_pptx_file)
    assert "SeekPal" in doc.text
    assert doc.extractor == "pptx"
    assert doc.page_map == []


def test_supported_extensions():
    ext = PptxExtractor()
    assert ".pptx" in ext.supported_extensions()
