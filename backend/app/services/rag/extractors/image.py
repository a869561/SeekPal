"""Extractor de imagen: OCR del texto incrustado + caption descriptivo."""

from __future__ import annotations

from pathlib import Path

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.image_service import extract_image_text
from app.services.rag.types import ExtractedDoc


class ImageExtractor(BaseExtractor):
    _EXTENSIONS = [
        ".png", ".jpg", ".jpeg", ".webp", ".bmp",
        ".tiff", ".tif", ".gif", ".avif",
    ]

    def extract(self, path: Path) -> ExtractedDoc:
        text = extract_image_text(path)
        return ExtractedDoc(text=text, page_map=[], extractor="image")

    def supported_extensions(self) -> list[str]:
        return self._EXTENSIONS
