from typing import Literal

from pydantic import BaseModel, Field

from app.models.config import OcrQuality, VisionModel, WhisperModel


class AddSourceRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SettingsPatch(BaseModel):
    theme: Literal["auto", "light", "dark"] | None = None
    fontSize: Literal["sm", "md", "lg"] | None = None
    language: Literal["es", "en"] | None = None
    # RAG / multimedia (requieren reinicio para que entren en efecto)
    rerankerEnabled: bool | None = None
    whisperModel: WhisperModel | None = None
    useDocling: bool | None = None
    indexMultimedia: bool | None = None
    videoFrameInterval: int | None = Field(default=None, ge=1, le=600)
    videoMaxFrames: int | None = Field(default=None, ge=1, le=500)
    ocrQuality: OcrQuality | None = None
    visionModel: VisionModel | None = None
