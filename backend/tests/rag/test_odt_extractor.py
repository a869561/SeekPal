from pathlib import Path

from app.services.rag.extractors.odt import OdtExtractor


def test_extracts_text_from_odt(tmp_odt_file: Path):
    extractor = OdtExtractor()
    doc = extractor.extract(tmp_odt_file)
    assert "SeekPal" in doc.text
    assert doc.extractor == "odt"
    assert doc.page_map == []


def test_supported_extensions():
    ext = OdtExtractor()
    assert ".odt" in ext.supported_extensions()
