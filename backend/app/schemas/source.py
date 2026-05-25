from pydantic import BaseModel, Field


class AddSourceRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SettingsPatch(BaseModel):
    theme: str | None = None
    fontSize: str | None = None
    language: str | None = None
    # RAG / multimedia (requieren reinicio para que entren en efecto)
    rerankerEnabled: bool | None = None
    whisperModel: str | None = None
    indexMultimedia: bool | None = None
    videoFrameInterval: int | None = None
    videoMaxFrames: int | None = None
