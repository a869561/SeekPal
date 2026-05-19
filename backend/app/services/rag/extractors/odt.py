from __future__ import annotations

from pathlib import Path

from odf.opendocument import load
from odf.text import P

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc


class OdtExtractor(BaseExtractor):
    def extract(self, path: Path) -> ExtractedDoc:
        doc = load(str(path))
        parts: list[str] = []
        for elem in doc.text.getElementsByType(P):
            line = "".join(
                node.data for node in elem.childNodes
                if hasattr(node, "data")
            ).strip()
            if line:
                parts.append(line)
        text = "\n".join(parts)
        return ExtractedDoc(text=text, page_map=[], extractor="odt")

    def supported_extensions(self) -> list[str]:
        return [".odt"]
