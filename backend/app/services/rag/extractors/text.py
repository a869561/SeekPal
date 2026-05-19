from __future__ import annotations

from pathlib import Path

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


class TextExtractor(BaseExtractor):
    _EXTENSIONS = [".txt", ".md", ".html", ".css", ".js", ".ts", ".json",
                   ".xml", ".csv", ".py", ".java", ".go", ".yaml", ".yml",
                   ".toml", ".ini", ".cfg", ".rst", ".tex"]

    def extract(self, path: Path) -> ExtractedDoc:
        text = path.read_text(encoding="utf-8", errors="replace")
        return ExtractedDoc(text=text, page_map=[], extractor="text")

    def supported_extensions(self) -> list[str]:
        return self._EXTENSIONS
