from __future__ import annotations

from pathlib import Path

import fitz

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


class PdfExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
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
