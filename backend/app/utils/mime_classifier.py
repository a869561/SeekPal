"""Clasificación MIME y categorización de ficheros indexables.

Los conjuntos de extensiones se mantienen alineados con la versión original Node
para preservar la compatibilidad con los datos ya ingestados.
"""

import mimetypes
from pathlib import Path
from typing import Literal


FileCategory = Literal["text", "document", "image", "audio", "video", "other"]

# --- Content-based text detection (git-style heuristic) ---
_SNIFF_BYTES = 8192
_BINARY_CTRL = frozenset(range(0x00, 0x09)) | frozenset(range(0x0E, 0x20)) | {0x7F}


def _looks_like_text(path: Path) -> bool:
    """Returns True if the file's first 8 KB looks like plain text."""
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


TEXT_EXTENSIONS = frozenset({
    ".txt", ".md", ".markdown", ".html", ".htm", ".css", ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".jsx", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".env", ".sh", ".bat", ".ps1", ".sql", ".csv",
    ".tsv", ".log", ".py", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".php", ".rb", ".swift", ".kt", ".r", ".m", ".tex", ".rst",
})

DOCUMENT_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".doc", ".odt", ".ods", ".odp",
    ".pptx", ".ppt", ".xlsx", ".xls", ".rtf", ".epub",
})

IMAGE_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".svg", ".bmp", ".tiff", ".tif", ".ico", ".avif",
})

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".m4a", ".wav", ".ogg", ".oga", ".flac", ".aac", ".wma", ".opus", ".aiff",
})

VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".avi", ".mpeg", ".mpg", ".mov", ".mkv", ".webm", ".wmv", ".flv", ".m4v", ".3gp",
})


_ALL_EXTENSIONS = (
    TEXT_EXTENSIONS | DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS
    | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
)


def _ext(path: str | Path) -> str:
    return Path(path).suffix.lower()


def is_indexable(path: str | Path) -> bool:
    p = Path(path)
    if p.suffix.lower() in _ALL_EXTENSIONS:
        return True
    return _looks_like_text(p)


def classify(path: str | Path) -> tuple[FileCategory, str]:
    p = Path(path)
    ext = p.suffix.lower()
    mime_type, _ = mimetypes.guess_type(str(p))
    mime_type = mime_type or "application/octet-stream"

    if ext in TEXT_EXTENSIONS:
        return "text", mime_type
    if ext in DOCUMENT_EXTENSIONS:
        return "document", mime_type
    if ext in IMAGE_EXTENSIONS:
        return "image", mime_type
    if ext in AUDIO_EXTENSIONS:
        return "audio", mime_type
    if ext in VIDEO_EXTENSIONS:
        return "video", mime_type
    if _looks_like_text(p):
        return "text", "text/plain"
    return "other", mime_type
