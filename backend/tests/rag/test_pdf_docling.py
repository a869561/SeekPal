"""Smoke tests para el extractor Docling y el switcheo PyMuPDF <-> Docling.

No requiere docling instalado: los tests verifican el comportamiento de fallback
graceful (useDocling=True sin docling -> PyMuPDF) y el dispatch del wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.rag.extractors.pdf import PdfExtractor
from app.services.rag.extractors.pdf_docling import (
    DoclingPdfExtractor,
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
