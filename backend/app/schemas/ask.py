from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)
    source_id: str | None = None
    categories: list[str] | None = None


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
