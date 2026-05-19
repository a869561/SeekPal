from __future__ import annotations

from pathlib import Path

from docx import Document

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


class DocxExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return ExtractedDoc(text=text, page_map=[], extractor="docx")

    def supported_extensions(self) -> list[str]:
        return [".docx"]
