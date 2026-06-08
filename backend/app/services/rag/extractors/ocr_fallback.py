"""Detección de PDFs con capa de texto corrupta + fallback a OCR.

Algunos PDFs (típicamente firmados digitalmente o con fuentes subset sin un
ToUnicode CMap válido) tienen una capa de texto que se RENDERIZA bien pero cuyo
mapeo glifo→Unicode es basura: PyMuPDF devuelve códigos de glifo crudos
(montones de \\x03/\\x04 como separadores y caracteres de Latin Extended como
ĞůĂĐŝſŶ en vez de "elaboración"). El documento parece tener texto, así que las
heurísticas de "PDF escaneado" basadas en cantidad de caracteres NO lo detectan.

Aquí medimos dos señales que son ~0 en texto sano y muy altas en este gibberish:
  - ratio de caracteres de control C0 (excluyendo tab/newline/cr)
  - ratio de caracteres en Latin Extended-A/B (0x100–0x24F), rarísimos en
    español/inglés (las tildes á é í ó ñ viven en Latin-1, 0xC0–0xFF, no aquí).

Cuando se detecta, se re-extrae rasterizando cada página y pasándola por el OCR
ya existente (RapidOCR de image_service), que lee los glifos visualmente y
recupera el texto correcto.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import fitz

from app.services.rag.types import ExtractedDoc

logger = logging.getLogger("seekpal.pdf")

# C0 controls salvo \t \n \r \x0b \x0c — casi nunca en una capa de texto sana.
_CTRL = set(range(0x00, 0x09)) | {0x0B, 0x0C} | set(range(0x0E, 0x20)) | {0x7F}

# Umbrales calibrados sobre el corpus: gibberish ~0.09 ctrl / ~0.31 latinext;
# todos los PDFs sanos dan 0.000 / 0.000. Hay margen de sobra.
_CTRL_THRESHOLD = 0.02
_LATIN_EXT_THRESHOLD = 0.10

# DPI de rasterizado para el OCR (200 = buen equilibrio calidad/velocidad).
_OCR_DPI = 200


def looks_garbled(text: str) -> bool:
    """True si la capa de texto parece corrupta (cmap roto), no texto real."""
    if not text or not text.strip():
        return False
    ctrl_ratio = sum(1 for c in text if ord(c) in _CTRL) / len(text)
    non_space = [c for c in text if not c.isspace()]
    latin_ext_ratio = (
        sum(1 for c in non_space if 0x100 <= ord(c) <= 0x24F) / len(non_space)
        if non_space else 0.0
    )
    return ctrl_ratio > _CTRL_THRESHOLD or latin_ext_ratio > _LATIN_EXT_THRESHOLD


def ocr_pdf(path: Path, dpi: int = _OCR_DPI) -> ExtractedDoc:
    """Re-extrae un PDF rasterizando cada página y pasándola por OCR.

    Reutiliza ocr_image() de image_service (RapidOCR), así comparte la carga
    lazy del motor y la configuración mobile/server. Devuelve extractor
    'pdf-ocr' para distinguirlo en logs y stats.
    """
    from app.services.rag.image_service import ocr_image

    doc = fitz.open(str(path))
    try:
        parts: list[str] = []
        page_map: list[tuple[int, int]] = []
        offset = 0
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        with tempfile.TemporaryDirectory(prefix="seekpal_pdfocr_") as tmp:
            tmpdir = Path(tmp)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=matrix)
                img_path = tmpdir / f"p{i}.png"
                pix.save(str(img_path))
                text = ocr_image(img_path)
                page_map.append((i, offset))
                parts.append(text)
                offset += len(text)
        return ExtractedDoc(text="\n".join(parts), page_map=page_map, extractor="pdf-ocr")
    finally:
        doc.close()
