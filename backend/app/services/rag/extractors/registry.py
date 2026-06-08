from __future__ import annotations

from pathlib import Path

from app.services.rag.extractors.audio import AudioExtractor
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.extractors.doc import DocExtractor
from app.services.rag.extractors.docx import DocxExtractor
from app.services.rag.extractors.epub import EpubExtractor
from app.services.rag.extractors.image import ImageExtractor
from app.services.rag.extractors.odp import OdpExtractor
from app.services.rag.extractors.ods import OdsExtractor
from app.services.rag.extractors.odt import OdtExtractor
from app.services.rag.extractors.pdf import PdfExtractor
from app.services.rag.extractors.ppt import PptExtractor
from app.services.rag.extractors.pptx import PptxExtractor
from app.services.rag.extractors.rtf import RtfExtractor
from app.services.rag.extractors.svg import SvgExtractor
from app.services.rag.extractors.text import TextExtractor, is_text_file
from app.services.rag.extractors.video import VideoExtractor
from app.services.rag.extractors.xlsx import XlsxExtractor


class UnsupportedFormatError(Exception):
    pass


_TEXT = TextExtractor()

_EXTRACTORS: list[BaseExtractor] = [
    _TEXT,
    PdfExtractor(),
    DocxExtractor(),
    DocExtractor(),
    PptxExtractor(),
    PptExtractor(),
    OdtExtractor(),
    OdsExtractor(),
    OdpExtractor(),
    XlsxExtractor(),
    RtfExtractor(),
    EpubExtractor(),
    SvgExtractor(),
    AudioExtractor(),
    ImageExtractor(),
    VideoExtractor(),
]

_EXTENSION_MAP: dict[str, BaseExtractor] = {
    ext: extractor
    for extractor in _EXTRACTORS
    for ext in extractor.supported_extensions()
}


def get_extractor(extension: str, category: str = "", path: Path | None = None) -> BaseExtractor | None:
    """Resuelve el extractor adecuado.

    1. Consulta el mapa de extensiones conocidas (fast path).
    2. Si la extensión no está en el mapa y se proporciona `path`,
       aplica detección heurística de texto (sniff de primeros 8 KB).
    """
    suffix = (extension or "").lower()
    if suffix in _EXTENSION_MAP:
        return _EXTENSION_MAP[suffix]
    if path is not None and is_text_file(path):
        return _TEXT
    return None
