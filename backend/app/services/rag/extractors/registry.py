from __future__ import annotations

from pathlib import Path

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.extractors.docx import DocxExtractor
from app.services.rag.extractors.odt import OdtExtractor
from app.services.rag.extractors.pdf import PdfExtractor
from app.services.rag.extractors.pptx import PptxExtractor
from app.services.rag.extractors.text import TextExtractor


class UnsupportedFormatError(Exception):
    pass


_EXTRACTORS: list[BaseExtractor] = [
    TextExtractor(),
    PdfExtractor(),
    DocxExtractor(),
    PptxExtractor(),
    OdtExtractor(),
]

_EXTENSION_MAP: dict[str, BaseExtractor] = {
    ext: extractor
    for extractor in _EXTRACTORS
    for ext in extractor.supported_extensions()
}


def get_extractor(extension_or_path, category: str = "") -> BaseExtractor | None:
    """Resuelve el extractor por extensión.

    Acepta Path (modo legacy: lanza UnsupportedFormatError si no soportado)
    o str (devuelve None si no soportado).
    """
    if isinstance(extension_or_path, Path):
        suffix = extension_or_path.suffix.lower()
        if suffix not in _EXTENSION_MAP:
            raise UnsupportedFormatError(f"No extractor for extension: {suffix!r}")
        return _EXTENSION_MAP[suffix]

    suffix = (extension_or_path or "").lower()
    return _EXTENSION_MAP.get(suffix)
