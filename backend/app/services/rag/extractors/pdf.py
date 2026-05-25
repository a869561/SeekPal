from __future__ import annotations

from pathlib import Path

import fitz

from app.core import runtime_settings
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.extractors.pdf_docling import (
    DoclingPdfExtractor,
    is_docling_installed,
)
from app.services.rag.types import ExtractedDoc


class PdfExtractor(BaseExtractor):
    """Extractor PDF con dos backends:

    - PyMuPDF (defecto): rapido (<100 ms/pagina), texto crudo.
    - Docling (opt-in): layout-aware, preserva tablas y multi-columna, hace
      OCR de paginas escaneadas. ~30x mas lento.

    El backend se elige en runtime por cada PDF segun el flag `useDocling`
    de UserSettings (cargado a runtime_settings al arrancar). Si docling no
    esta instalado, cae a PyMuPDF aunque el flag este activo (con un log).
    """

    def __init__(self) -> None:
        self._docling: DoclingPdfExtractor | None = None

    def extract(self, path: Path) -> ExtractedDoc:
        if runtime_settings.get("useDocling", False):
            if is_docling_installed():
                if self._docling is None:
                    self._docling = DoclingPdfExtractor()
                return self._docling.extract(path)
            else:
                print(
                    "[seekpal] useDocling=True pero docling no esta instalado — "
                    "instala con 'pip install docling' o desde Settings → "
                    "Activar PDF avanzado. Cayendo a PyMuPDF."
                )

        # Fallback PyMuPDF (rapido, texto crudo)
        doc = fitz.open(str(path))
        try:
            parts: list[str] = []
            page_map: list[tuple[int, int]] = []
            offset = 0
            for i, page in enumerate(doc, start=1):
                page_map.append((i, offset))
                text = page.get_text("text")
                parts.append(text)
                offset += len(text)
            full_text = "".join(parts)
        finally:
            doc.close()
        return ExtractedDoc(text=full_text, page_map=page_map, extractor="pdf")

    def supported_extensions(self) -> list[str]:
        return [".pdf"]
