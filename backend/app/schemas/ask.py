from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    source_id: str | None = None
    categories: list[str] | None = None
    # Solo para la evaluación offline (RAGAS): si True, el evento "retrieved"
    # incluye el texto COMPLETO de cada chunk (no el snippet de 200 chars), para
    # medir faithfulness/recall contra lo que vio el LLM de verdad.
    full_context: bool = False


class Citation(BaseModel):
    chunk_id: str
    file_id: str
    file_name: str
    page: int | None
    snippet: str
    score: float


class AskHealth(BaseModel):
    ollama: dict
    qdrant: dict
    mongo: dict
