"""Extractor para libros electrónicos (.epub).

Usa ebooklib para leer el contenido XHTML de cada capítulo.
El HTML se limpia con html.parser (stdlib, sin dependencias extra).
"""
from __future__ import annotations

import logging
from html.parser import HTMLParser
from pathlib import Path

import ebooklib
from ebooklib import epub

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

# ebooklib emite warnings de libxml2 en algunos epubs; silenciarlos
logging.getLogger("ebooklib").setLevel(logging.ERROR)


class _StripHtml(HTMLParser):
    """Extrae el texto plano de un fragmento HTML."""

    SKIP_TAGS = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


class EpubExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
        parts: list[str] = []

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            html = item.get_content().decode("utf-8", errors="ignore")
            parser = _StripHtml()
            parser.feed(html)
            text = parser.get_text().strip()
            if text:
                parts.append(text)

        return ExtractedDoc(
            text="\n\n".join(parts),
            page_map=[],
            extractor="epub",
        )

    def supported_extensions(self) -> list[str]:
        return [".epub"]
