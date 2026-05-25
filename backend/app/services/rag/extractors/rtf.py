"""Extractor para Rich Text Format (.rtf).

Usa striprtf, librería pura Python sin dependencias externas.
"""
from __future__ import annotations

from pathlib import Path

from striprtf.striprtf import rtf_to_text

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


class RtfExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        # RTF es siempre Latin-1 / Windows-1252 a nivel de fichero
        raw = path.read_text(encoding="latin-1", errors="ignore")
        text = rtf_to_text(raw, encoding="utf-8", errors="ignore")
        return ExtractedDoc(text=text.strip(), page_map=[], extractor="rtf")

    def supported_extensions(self) -> list[str]:
        return [".rtf"]
