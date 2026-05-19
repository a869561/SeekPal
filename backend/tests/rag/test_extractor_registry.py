from pathlib import Path

import pytest

from app.services.rag.extractors.registry import get_extractor, UnsupportedFormatError


def test_resolves_txt():
    ext = get_extractor(Path("file.txt"))
    assert ext.__class__.__name__ == "TextExtractor"


def test_resolves_pdf():
    ext = get_extractor(Path("file.pdf"))
    assert ext.__class__.__name__ == "PdfExtractor"


def test_resolves_docx():
    ext = get_extractor(Path("file.docx"))
    assert ext.__class__.__name__ == "DocxExtractor"


def test_resolves_pptx():
    ext = get_extractor(Path("file.pptx"))
    assert ext.__class__.__name__ == "PptxExtractor"


def test_resolves_odt():
    ext = get_extractor(Path("file.odt"))
    assert ext.__class__.__name__ == "OdtExtractor"


def test_raises_for_unsupported():
    with pytest.raises(UnsupportedFormatError):
        get_extractor(Path("file.mp4"))
