from pathlib import Path

from app.services.rag.extractors.registry import get_extractor


def test_resolves_txt():
    ext = get_extractor(".txt")
    assert ext.__class__.__name__ == "TextExtractor"


def test_resolves_pdf():
    ext = get_extractor(".pdf")
    assert ext.__class__.__name__ == "PdfExtractor"


def test_resolves_docx():
    ext = get_extractor(".docx")
    assert ext.__class__.__name__ == "DocxExtractor"


def test_resolves_pptx():
    ext = get_extractor(".pptx")
    assert ext.__class__.__name__ == "PptxExtractor"


def test_resolves_odt():
    ext = get_extractor(".odt")
    assert ext.__class__.__name__ == "OdtExtractor"


def test_resolves_mp3():
    ext = get_extractor(".mp3")
    assert ext.__class__.__name__ == "AudioExtractor"


def test_resolves_png():
    ext = get_extractor(".png")
    assert ext.__class__.__name__ == "ImageExtractor"


def test_resolves_mp4():
    ext = get_extractor(".mp4")
    assert ext.__class__.__name__ == "VideoExtractor"


def test_returns_none_for_unsupported():
    # Extensiones no cubiertas por ningun extractor (ej. binarios opacos)
    result = get_extractor(".exe")
    assert result is None


def test_resolves_txt_via_path_sniff(tmp_path: Path):
    """Archivos sin extensión conocida se detectan por contenido si son texto."""
    f = tmp_path / "noext"
    f.write_text("hola mundo", encoding="utf-8")
    ext = get_extractor("", path=f)
    assert ext is not None and ext.__class__.__name__ == "TextExtractor"
