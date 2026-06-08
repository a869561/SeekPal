from pathlib import Path

from app.services.rag.extractors.registry import get_extractor
from app.services.rag.extractors.svg import SvgExtractor

_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">
  <style>.lbl { font-family: Roboto, sans-serif; color: rgb(60,120,216); }</style>
  <title>Diagrama de navegacion</title>
  <rect x="0" y="0" width="50" height="50" style="fill: blue; stroke: red;"/>
  <text x="10" y="20" style="font-weight: 400;" class="lbl">Menu principal</text>
  <foreignObject width="80" height="30">
    <div xmlns="http://www.w3.org/1999/xhtml" style="color: green;">Pausa</div>
  </foreignObject>
</svg>"""


def test_extracts_visible_text(tmp_path: Path):
    p = tmp_path / "diagram.svg"
    p.write_text(_SVG, encoding="utf-8")
    doc = SvgExtractor().extract(p)
    assert doc.extractor == "svg"
    assert "Diagrama de navegacion" in doc.text
    assert "Menu principal" in doc.text
    assert "Pausa" in doc.text  # texto HTML dentro de foreignObject


def test_ignores_css_and_style_noise(tmp_path: Path):
    p = tmp_path / "diagram.svg"
    p.write_text(_SVG, encoding="utf-8")
    text = SvgExtractor().extract(p).text
    # Ni el contenido de <style> ni los atributos style= deben filtrarse
    assert "font-family" not in text
    assert "Roboto" not in text
    assert "rgb(" not in text
    assert "fill" not in text


def test_malformed_svg_falls_back_without_css(tmp_path: Path):
    p = tmp_path / "broken.svg"
    p.write_text(
        '<svg><style>.x{color:red}</style><text>Nodo</text><unclosed>',
        encoding="utf-8",
    )
    text = SvgExtractor().extract(p).text
    assert "Nodo" in text
    assert "color:red" not in text  # el bloque <style> se elimina en el fallback


def test_svg_routes_to_dedicated_extractor():
    assert isinstance(get_extractor(".svg"), SvgExtractor)


def test_supported_extensions():
    assert SvgExtractor().supported_extensions() == [".svg"]
