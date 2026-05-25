from __future__ import annotations

from pathlib import Path

from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

_SNIFF_BYTES = 8192
# Bytes that indicate binary content (C0 controls excluding \t \n \r \x0b \x0c)
_BINARY_CTRL = set(range(0x00, 0x09)) | set(range(0x0E, 0x20)) | {0x7F}


def is_text_file(path: Path) -> bool:
    """Returns True if the file looks like plain text (git-style heuristic).

    Reads the first 8 KB and checks:
    - No null bytes (0x00) → definite binary marker
    - Fewer than 5 % control characters → assume text
    """
    try:
        sample = path.read_bytes()[:_SNIFF_BYTES]
    except OSError:
        return False
    if not sample:
        return False
    if 0x00 in sample:
        return False
    ctrl = sum(1 for b in sample if b in _BINARY_CTRL)
    return ctrl / len(sample) < 0.05


class TextExtractor(BaseExtractor):
    # Well-known extensions for fast-path lookup (no sniffing needed).
    # Unknown extensions fall back to is_text_file() in the registry.
    _EXTENSIONS = [
        ".txt", ".md", ".rst", ".tex", ".html", ".xml",
        ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv",
        ".css", ".js", ".ts", ".jsx", ".tsx",
        ".c", ".h", ".cpp", ".hpp", ".cs", ".java", ".go",
        ".py", ".rb", ".lua", ".sh", ".bat", ".ps1",
        ".sql", ".r", ".kt", ".swift",
    ]

    def extract(self, path: Path) -> ExtractedDoc:
        text = path.read_text(encoding="utf-8", errors="replace")
        return ExtractedDoc(text=text, page_map=[], extractor="text")

    def supported_extensions(self) -> list[str]:
        return self._EXTENSIONS
