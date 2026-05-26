"""Extractor PDF basado en Docling (layout-aware).

A diferencia de PyMuPDF (extraccion de texto crudo pagina a pagina), Docling:
  - Identifica titulos, parrafos, listas, tablas y figuras con un modelo de
    layout (DocLayNet).
  - Reconstruye tablas como Markdown (filas y columnas preservadas).
  - Lee multi-columna correctamente.
  - Hace OCR de paginas escaneadas via RapidOCR integrado.
  - Exporta el documento estructurado a Markdown (titulos jerarquicos H1-H6).

Coste: ~3-10 s/pagina con CPU vs <100 ms/pagina de PyMuPDF (~30x mas lento).
Solo merece la pena para corpora con tablas, papers academicos multi-columna
o PDFs escaneados. Por eso es opt-in.

Carga lazy via LazyService — el primer PDF tarda ~10-20s extra mientras se
inicializan los modelos de Docling (~2 GB descargados en primera ejecucion).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.rag._lazy import LazyService
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

logger = logging.getLogger("seekpal.docling")


def _load_converter() -> "DocumentConverter":
    from docling.document_converter import DocumentConverter
    logger.info("Docling: cargando modelos de layout (DocLayNet)...")
    converter = DocumentConverter()
    logger.info("Docling: listo")
    return converter


_converter = LazyService("Docling", _load_converter)

# Registrar para que get_model_status() lo incluya en el estado global
from app.services.rag._lazy import register as _register  # noqa: E402
_register(_converter)


def is_docling_installed() -> bool:
    """True si la dependencia docling esta importable (sin cargarla)."""
    import importlib.util
    return importlib.util.find_spec("docling") is not None


class DoclingPdfExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        converter = _converter.get()
        if converter is None:
            # docling no instalado o fallo al cargar. Devuelve doc vacio para
            # que prepare_file caiga al fallback (pdf.PdfExtractor maneja la
            # eleccion antes de llegar aqui, asi que esto es defense in depth).
            return ExtractedDoc(text="", page_map=[], extractor="docling-failed")

        result = converter.convert(str(path))
        markdown = result.document.export_to_markdown()

        # Docling no expone offsets pagina por pagina en el markdown final.
        # Para cumplir el contrato de ExtractedDoc reconstruimos un page_map
        # aproximado contando paginas via la API de DoclingDocument.
        page_map: list[tuple[int, int]] = []
        try:
            num_pages = len(result.document.pages)
            if num_pages > 0:
                avg_chars = max(1, len(markdown) // num_pages)
                page_map = [(i + 1, i * avg_chars) for i in range(num_pages)]
        except Exception:
            pass  # page_map vacio es valido — chunks tendran page=None

        return ExtractedDoc(text=markdown, page_map=page_map, extractor="docling")

    def supported_extensions(self) -> list[str]:
        return [".pdf"]
