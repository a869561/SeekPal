from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExtractedDoc:
    text: str
    page_map: list[tuple[int, int]] = field(default_factory=list)
    extractor: str = ""


@dataclass(slots=True)
class Chunk:
    text: str
    chunk_idx: int
    offset_start: int
    offset_end: int
    page: int | None = None


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: str
    file_id: str
    source_id: str
    text: str
    page: int | None
    offset_start: int
    offset_end: int
    file_name: str
    category: str
    extension: str
    score: float
