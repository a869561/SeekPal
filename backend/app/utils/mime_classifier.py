"""Clasificación MIME y categorización de ficheros indexables.

Los conjuntos de extensiones se mantienen alineados con la versión original Node
para preservar la compatibilidad con los datos ya ingestados.
"""

import mimetypes
from pathlib import Path
from typing import Literal


FileCategory = Literal["text", "document", "image", "audio", "video", "other"]


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
    return _ext(path) in _ALL_EXTENSIONS


def classify(path: str | Path) -> tuple[FileCategory, str]:
    ext = _ext(path)
    mime_type, _ = mimetypes.guess_type(str(path))
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
    return "other", mime_type
