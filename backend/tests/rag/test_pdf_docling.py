"""Smoke tests para el extractor Docling y el switcheo PyMuPDF <-> Docling.

No requiere docling instalado: los tests verifican el comportamiento de fallback
graceful (useDocling=True sin docling -> PyMuPDF) y el dispatch del wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.rag.extractors.pdf import PdfExtractor
from app.services.rag.extractors.pdf_docling import (
    DoclingPdfExtractor,
    _converter_digital,
    _converter_scanned,
    is_docling_installed,
)


def test_docling_extractor_extensions():
    assert DoclingPdfExtractor().supported_extensions() == [".pdf"]


def test_is_docling_installed_returns_bool():
    """No depende de si esta instalado o no, solo de que devuelva un bool."""
    result = is_docling_installed()
    assert isinstance(result, bool)


def test_pdf_extractor_uses_pymupdf_by_default(tmp_path: Path):
    """Sin runtime_settings.useDocling activo, se usa PyMuPDF."""
    import fitz
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 80), "Hola mundo en PDF")
    doc.save(str(pdf_path))
    doc.close()

    from app.core import runtime_settings
    original = runtime_settings._settings.get("useDocling")
    try:
        runtime_settings._settings["useDocling"] = False
        result = PdfExtractor().extract(pdf_path)
        assert result.extractor == "pdf"  # PyMuPDF
        assert "Hola mundo" in result.text
    finally:
        runtime_settings._settings["useDocling"] = original or False


def test_pdf_extractor_falls_back_when_docling_missing(tmp_path: Path):
    """Si useDocling=True pero docling no esta instalado, cae a PyMuPDF."""
    import fitz
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 80), "Fallback test")
    doc.save(str(pdf_path))
    doc.close()

    from app.core import runtime_settings
    from app.services.rag.extractors import pdf as pdf_mod

    original = runtime_settings._settings.get("useDocling")
    try:
        runtime_settings._settings["useDocling"] = True
        with patch.object(pdf_mod, "is_docling_installed", return_value=False):
            result = PdfExtractor().extract(pdf_path)
            assert result.extractor == "pdf"  # PyMuPDF, no docling
            assert "Fallback test" in result.text
    finally:
        runtime_settings._settings["useDocling"] = original or False


def test_pdf_extractor_uses_docling_when_active_and_installed(tmp_path: Path):
    """Si useDocling=True y docling esta instalado, delega al DoclingPdfExtractor."""
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-fake")  # contenido irrelevante para este mock

    from app.core import runtime_settings
    from app.services.rag.extractors import pdf as pdf_mod
    from app.services.rag.types import ExtractedDoc

    original = runtime_settings._settings.get("useDocling")
    fake_doc = ExtractedDoc(text="Tabla\n| a | b |\n| 1 | 2 |", page_map=[], extractor="docling")

    try:
        runtime_settings._settings["useDocling"] = True
        with patch.object(pdf_mod, "is_docling_installed", return_value=True), \
             patch.object(DoclingPdfExtractor, "extract", return_value=fake_doc):
            result = PdfExtractor().extract(pdf_path)
            assert result.extractor == "docling"
            assert "Tabla" in result.text
    finally:
        runtime_settings._settings["useDocling"] = original or False


# ---------------------------------------------------------------------------
# Routing escaneado vs digital (dos converters con do_ocr/images_scale distinto)
# ---------------------------------------------------------------------------

def _reset(svc):
    svc._instance = None
    svc._disabled = False
    svc._loading = False


@pytest.fixture
def reset_converters():
    """Resetea el estado de ambos LazyService entre tests.

    LazyService usa __slots__, asi que no se puede hacer patch.object sobre el
    metodo get(); en su lugar inyectamos directamente _instance / _disabled.
    """
    _reset(_converter_digital)
    _reset(_converter_scanned)
    yield
    _reset(_converter_digital)
    _reset(_converter_scanned)


def _fake_converter():
    fake = MagicMock()
    fake.convert.return_value.document.export_to_markdown.return_value = "texto"
    fake.convert.return_value.document.pages = []
    return fake


def test_both_converters_are_lazy_services():
    from app.services.rag._lazy import LazyService
    assert isinstance(_converter_digital, LazyService)
    assert isinstance(_converter_scanned, LazyService)
    assert _converter_digital._name == "Docling"
    assert _converter_scanned._name == "Docling-OCR"


def test_loaders_are_callable():
    from app.services.rag.extractors import pdf_docling
    assert callable(pdf_docling._load_converter_digital)
    assert callable(pdf_docling._load_converter_scanned)


def test_scanned_detection_returns_bool():
    from app.services.rag.extractors.pdf_docling import _pdf_is_scanned
    assert isinstance(_pdf_is_scanned(Path("dummy.pdf")), bool)


def test_missing_file_is_not_scanned():
    """Ante un fichero ilegible asumimos digital (no forzar OCR caro)."""
    from app.services.rag.extractors.pdf_docling import _pdf_is_scanned
    assert _pdf_is_scanned(Path("no_existe_xyz.pdf")) is False


def test_extract_returns_empty_when_converter_unavailable(reset_converters):
    """Si el converter no carga (docling ausente), devuelve doc vacio."""
    _converter_digital._disabled = True  # get() devolvera None
    with patch(
        "app.services.rag.extractors.pdf_docling._pdf_is_scanned",
        return_value=False,
    ):
        doc = DoclingPdfExtractor().extract(Path("dummy.pdf"))
    assert doc.text == ""
    assert doc.extractor == "docling-failed"


def test_digital_pdf_uses_digital_converter(reset_converters):
    dig, scan = _fake_converter(), _fake_converter()
    _converter_digital._instance = dig
    _converter_scanned._instance = scan
    with patch(
        "app.services.rag.extractors.pdf_docling._pdf_is_scanned",
        return_value=False,
    ):
        DoclingPdfExtractor().extract(Path("dummy.pdf"))
    dig.convert.assert_called_once()
    scan.convert.assert_not_called()


def test_scanned_pdf_uses_scanned_converter(reset_converters):
    dig, scan = _fake_converter(), _fake_converter()
    _converter_digital._instance = dig
    _converter_scanned._instance = scan
    with patch(
        "app.services.rag.extractors.pdf_docling._pdf_is_scanned",
        return_value=True,
    ):
        DoclingPdfExtractor().extract(Path("dummy.pdf"))
    scan.convert.assert_called_once()
    dig.convert.assert_not_called()
