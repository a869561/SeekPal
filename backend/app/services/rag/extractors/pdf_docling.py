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

Perfiles segun escaneado vs digital
-----------------------------------
Renderizar paginas a alta resolucion para el OCR es lo que dispara el
`std::bad_alloc` en PDFs grandes (>~28 paginas). Pero esos PDFs grandes casi
siempre son DIGITALES (texto embebido), donde el OCR es inutil. Por eso
detectamos el tipo de PDF con PyMuPDF y elegimos uno de dos converters:

  - DIGITAL  -> do_ocr=False, images_scale=1.0 (minimo). Sin OCR no hay OOM y
               no se pierde nada: el texto se extrae directo. Se mantiene la
               deteccion de tablas/multicolumna (do_table_structure=True).
  - ESCANEADO -> do_ocr=True, images_scale=2.0 (alta). Necesita OCR de calidad;
               al ser tipicamente de pocas paginas la memoria esta acotada.

La palanca decisiva contra el OOM es do_ocr=False en los digitales; images_scale
es el ajuste secundario (minimo en digital, alto en escaneado).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import fitz

from app.services.rag._lazy import LazyService
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.extractors.ocr_fallback import looks_garbled, ocr_pdf
from app.services.rag.types import ExtractedDoc

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

logger = logging.getLogger("seekpal.docling")

# Resolucion de renderizado por perfil (multiplicador sobre 72 DPI):
#   1.0 = 72 DPI (minimo), 2.0 = 144 DPI (buen OCR de texto impreso).
_SCALE_DIGITAL = 1.0
_SCALE_SCANNED = 2.0

# Heuristica de deteccion escaneado vs digital (ver _pdf_is_scanned).
_SAMPLE_PAGES = 5
_MIN_CHARS_PER_PAGE = 50

# Umbral de tamaño: PDFs mas pesados tienen paginas con mucho contenido visual
# (imagenes embebidas, graficos) que Docling rasteriza por pagina para el analisis
# de layout, disparando OOM incluso sin OCR. Por encima de este limite se usa
# PyMuPDF directamente — mas rapido y sin limite de memoria.
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def _make_converter(*, do_ocr: bool, images_scale: float) -> "DocumentConverter":
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions(
        do_ocr=do_ocr,
        do_table_structure=True,
        images_scale=images_scale,
    )
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def _load_converter_digital() -> "DocumentConverter":
    logger.info("Docling: cargando modelos (perfil digital, sin OCR, scale=%.1f)...", _SCALE_DIGITAL)
    converter = _make_converter(do_ocr=False, images_scale=_SCALE_DIGITAL)
    logger.info("Docling: listo (digital)")
    return converter


def _load_converter_scanned() -> "DocumentConverter":
    logger.info("Docling: cargando modelos + OCR (perfil escaneado, scale=%.1f)...", _SCALE_SCANNED)
    converter = _make_converter(do_ocr=True, images_scale=_SCALE_SCANNED)
    logger.info("Docling: listo (escaneado)")
    return converter


# Dos converters lazy independientes. El digital se carga al ver el primer PDF
# digital; el de OCR solo si aparece un PDF escaneado (en muchos repos nunca).
_converter_digital = LazyService("Docling", _load_converter_digital)
_converter_scanned = LazyService("Docling-OCR", _load_converter_scanned)

# Registrar ambos para que get_model_status() los incluya en el estado global
from app.services.rag._lazy import register as _register  # noqa: E402
_register(_converter_digital)
_register(_converter_scanned)


def is_docling_installed() -> bool:
    """True si la dependencia docling esta importable (sin cargarla)."""
    import importlib.util
    return importlib.util.find_spec("docling") is not None


def _pdf_is_scanned(path: Path) -> bool:
    """Heuristica: un PDF necesita OCR si (a) es escaneado —paginas que son
    imagenes sin texto embebido— o (b) tiene la capa de texto corrupta (cmap
    roto en PDFs firmados/subset: parece tener texto, pero es gibberish).

    Muestreamos hasta _SAMPLE_PAGES paginas repartidas por el documento y
    medimos el texto extraible con PyMuPDF (<100 ms). Si la media de caracteres
    por pagina es muy baja → escaneado. Si hay texto pero looks_garbled() →
    capa corrupta. En ambos casos hace falta OCR a alta resolucion.

    Ante cualquier error o duda devolvemos False (digital): preferimos no
    forzar el OCR caro y arriesgar OOM en un PDF que en realidad tiene texto.
    """
    try:
        doc = fitz.open(str(path))
    except Exception:
        return False
    try:
        total = doc.page_count
        if total == 0:
            return False
        step = max(1, total // _SAMPLE_PAGES)
        idxs = list(range(0, total, step))[:_SAMPLE_PAGES]
        sample = "".join(doc[i].get_text("text") for i in idxs)
        if (len(sample.strip()) / len(idxs)) < _MIN_CHARS_PER_PAGE:
            return True  # escaneado: poco o nada de texto embebido
        return looks_garbled(sample)  # hay texto pero es basura → OCR
    except Exception:
        return False
    finally:
        doc.close()


class DoclingPdfExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        # PDFs grandes tienen paginas con mucho contenido visual: Docling las
        # rasteriza todas para el analisis de layout y se queda sin memoria.
        # El tamaño en disco es el proxy mas barato y fiable (stat(), <1 ms).
        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0
        if file_size > _MAX_FILE_BYTES:
            size_mb = file_size / (1024 * 1024)
            logger.info(
                "Docling: %s (%.0f MB) supera umbral de %d MB → PyMuPDF",
                path.name, size_mb, _MAX_FILE_BYTES // (1024 * 1024),
            )
            # Usar fitz directamente — no PdfExtractor().extract() porque éste
            # re-enruta a Docling cuando useDocling=True, creando recursión infinita.
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
            if looks_garbled(full_text):
                logger.info(
                    "PDF %s: capa de texto corrupta detectada → re-extrayendo con OCR",
                    path.name,
                )
                return ocr_pdf(path)
            return ExtractedDoc(text=full_text, page_map=page_map, extractor="pdf")

        scanned = _pdf_is_scanned(path)
        lazy = _converter_scanned if scanned else _converter_digital
        converter = lazy.get()
        if converter is None:
            # docling no instalado o fallo al cargar. Devuelve doc vacio para
            # que prepare_file caiga al fallback (pdf.PdfExtractor maneja la
            # eleccion antes de llegar aqui, asi que esto es defense in depth).
            return ExtractedDoc(text="", page_map=[], extractor="docling-failed")

        logger.info(
            "Docling: %s -> perfil %s",
            path.name,
            "escaneado (OCR)" if scanned else "digital (sin OCR)",
        )
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
