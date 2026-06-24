from typing import Literal

from pydantic import BaseModel, Field

from app.models.config import DeviceOverride, OcrQuality, ProcessingPriority


class AddSourceRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SettingsPatch(BaseModel):
    theme: Literal["auto", "light", "dark"] | None = None
    fontSize: Literal["sm", "md", "lg"] | None = None
    language: Literal["es", "en"] | None = None
    # RAG / multimedia (requieren reinicio para que entren en efecto)
    rerankerEnabled: bool | None = None
    whisperModel: str | None = None
    llmModel: str | None = None
    useDocling: bool | None = None
    indexMultimedia: bool | None = None
    videoFrameInterval: int | None = Field(default=None, ge=1, le=600)
    videoMaxFrames: int | None = Field(default=None, ge=1, le=500)
    ocrQuality: OcrQuality | None = None
    visionModel: str | None = None
    autoFreePreviousVisionModel: bool | None = None
    # Planificador de dispositivos VRAM-aware (requiere reinicio).
    processingPriority: ProcessingPriority | None = None
    # Overrides manuales por componente. Claves: "embeddings","reranker","whisper","ocr".
    deviceOverrides: dict[str, DeviceOverride] | None = None
