"""Extractor para presentaciones OpenDocument (.odp).

Usa odfpy (ya instalado para OdtExtractor).
Extrae texto de cada diapositiva en orden, incluyendo notas del presentador.
"""
from __future__ import annotations

from pathlib import Path

from odf.draw import Frame, Page
from odf.opendocument import load
from odf.presentation import Notes
from odf.text import P

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


def _texts_from(element) -> list[str]:
    """Extrae todos los párrafos de texto de un elemento ODF."""
    lines = []
    for p in element.getElementsByType(P):
        line = "".join(
            node.data for node in p.childNodes if hasattr(node, "data")
        ).strip()
        if line:
            lines.append(line)
    return lines


class OdpExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        doc = load(str(path))
        slides_text: list[str] = []

        for i, page in enumerate(doc.presentation.getElementsByType(Page), 1):
            parts: list[str] = []

            # Texto de frames (cuadros de texto, títulos, etc.)
            for frame in page.getElementsByType(Frame):
                parts.extend(_texts_from(frame))

            # Notas del presentador
            for notes in page.getElementsByType(Notes):
                note_lines = _texts_from(notes)
                if note_lines:
                    parts.append("[Notas] " + " ".join(note_lines))

            if parts:
                slides_text.append(f"[Diapositiva {i}]\n" + "\n".join(parts))

        text = "\n\n".join(slides_text)
        return ExtractedDoc(text=text, page_map=[], extractor="odp")

    def supported_extensions(self) -> list[str]:
        return [".odp"]
