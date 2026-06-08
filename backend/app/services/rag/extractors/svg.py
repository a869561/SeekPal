"""Extractor SVG: saca solo el texto VISIBLE del dibujo, no el markup.

Un SVG es XML de dibujo vectorial. El extractor de texto genérico lo volcaba
crudo (paths, atributos style="font-family: Roboto; color: ...", definiciones
CSS), generando decenas de chunks de basura sin valor para búsqueda. Aquí
parseamos el XML y recogemos únicamente el contenido textual:

  - <text>, <tspan>          -> etiquetas SVG nativas
  - <title>, <desc>          -> metadatos accesibles
  - contenido de <foreignObject> -> labels HTML de draw.io (div/span/...)

Se ignoran explícitamente <style> y <script>. Los atributos (incluido style=)
nunca aparecen en itertext(), así que el ruido CSS se elimina por construcción.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

# defusedxml endurece el parser contra XXE y billion-laughs (los SVG son
# ficheros de usuario, contenido no confiable). Solo cambia el parseo; los
# tipos/excepciones (Element, ParseError) siguen siendo los de stdlib.
from defusedxml.ElementTree import fromstring as _safe_fromstring

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

logger = logging.getLogger("seekpal.svg")

# Tags cuyo contenido textual NO queremos (CSS/JS embebido en el SVG).
_SKIP_TAGS = {"style", "script"}


def _localname(tag: str) -> str:
    """Devuelve el nombre local sin namespace: '{http://...}text' -> 'text'."""
    return tag.rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _collect_text(elem: ET.Element, out: list[str]) -> None:
    """Recorre el árbol acumulando texto, saltando subárboles style/script."""
    if _localname(elem.tag) in _SKIP_TAGS:
        return
    if elem.text and elem.text.strip():
        out.append(elem.text.strip())
    for child in elem:
        _collect_text(child, out)
        if child.tail and child.tail.strip():
            out.append(child.tail.strip())


def _strip_markup_fallback(raw: str) -> str:
    """Fallback si el XML está mal formado: elimina style/script y luego tags."""
    raw = re.sub(r"<style\b.*?</style>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


class SvgExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        raw = path.read_text(encoding="utf-8", errors="replace")
        try:
            root = _safe_fromstring(raw)
            parts: list[str] = []
            _collect_text(root, parts)
            text = "\n".join(parts)
        except ET.ParseError as exc:
            logger.warning("SVG %s mal formado (%s) — fallback a strip de tags", path.name, exc)
            text = _strip_markup_fallback(raw)
        return ExtractedDoc(text=text, page_map=[], extractor="svg")

    def supported_extensions(self) -> list[str]:
        return [".svg"]
