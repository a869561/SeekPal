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
    context: str = ""

    @property
    def embed_text(self) -> str:
        """Texto a embeddear: contexto de ruta (si existe) + texto del chunk.

        El contexto de ruta enriquece el embedding denso y sparse con tokens
        derivados del nombre del fichero y sus carpetas (relativo a la fuente).
        El payload/snippet sigue usando .text (limpio, sin contexto).
        """
        if self.context:
            return f"{self.context}\n{self.text}"
        return self.text


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
    context: str = ""

    @property
    def embed_text(self) -> str:
        """Texto enriquecido con contexto de ruta (igual que Chunk.embed_text).

        Usado por el reranker para puntuar con los mismos tokens que se
        indexaron, de modo que las imágenes con contexto de ruta no sean
        penalizadas respecto a lo que el retriever ya recuperó.
        El snippet/UI sigue usando .text (limpio, sin contexto).
        """
        if self.context:
            return f"{self.context}\n{self.text}"
        return self.text
