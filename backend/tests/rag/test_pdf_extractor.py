from pathlib import Path

from app.services.rag.extractors.pdf import PdfExtractor


def test_extracts_text_from_pdf(tmp_pdf_file: Path):
    extractor = PdfExtractor()
    doc = extractor.extract(tmp_pdf_file)
    assert "Página 1" in doc.text or "SeekPal" in doc.text
    assert doc.extractor == "pdf"


def test_page_map_has_two_entries(tmp_pdf_file: Path):
    extractor = PdfExtractor()
    doc = extractor.extract(tmp_pdf_file)
    assert len(doc.page_map) == 2


def test_page_map_first_entry(tmp_pdf_file: Path):
    extractor = PdfExtractor()
    doc = extractor.extract(tmp_pdf_file)
    page_num, offset = doc.page_map[0]
    assert page_num == 1
    assert offset == 0


def test_supported_extensions():
    ext = PdfExtractor()
    assert ".pdf" in ext.supported_extensions()
