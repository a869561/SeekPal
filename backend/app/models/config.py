from datetime import UTC, datetime
from typing import Literal

from beanie import Document, before_event
from beanie.odm.actions import Replace, Save, SaveChanges, Update
from pydantic import BaseModel, Field


WhisperModel = Literal["tiny", "base", "small", "medium", "large"]
OcrQuality   = Literal["mobile", "server"]
VisionModel  = Literal["qwen2.5vl:3b", "moondream"]


def _now_utc() -> datetime:
    return datetime.now(UTC)


class UserSettings(BaseModel):
    # Apariencia / cuenta
    theme: str = "auto"
    fontSize: str = "md"
    language: str = "es"

    # RAG — leidos al iniciar el backend. Cambios requieren reinicio (el reranker
    # y Whisper se cargan una vez por sesion).
    rerankerEnabled: bool = True
    whisperModel: WhisperModel = "small"

    # PDFs estructurados (Docling). Default OFF porque requiere ~2 GB de
    # dependencias (torch + transformers + modelos) — se instala on-demand
    # desde Settings. Si esta ON sin docling instalado, PdfExtractor cae a
    # PyMuPDF con un warning.
    useDocling: bool = False

    # Multimedia
    indexMultimedia: bool = True       # master switch para audio/imagen/video
    videoFrameInterval: int = Field(default=30, ge=1, le=600)
    videoMaxFrames: int = Field(default=20, ge=1, le=500)
    ocrQuality: OcrQuality = "mobile"  # mobile=rápido (~15 MB) | server=preciso (~140 MB)
    visionModel: VisionModel = "qwen2.5vl:3b"  # qwen2.5vl:3b=mejor calidad (default) | moondream=más rápido
    # Al cambiar de modelo de visión, desinstalar el anterior para ahorrar disco.
    # Por defecto OFF: cambiar a menudo no debe re-descargar GB cada vez. Nunca
    # toca el modelo de respaldo (moondream) ni el LLM activo.
    autoFreePreviousVisionModel: bool = False


class Config(Document):
    passwordHash: str
    settings: UserSettings = Field(default_factory=UserSettings)
    createdAt: datetime = Field(default_factory=_now_utc)
    updatedAt: datetime = Field(default_factory=_now_utc)

    @before_event(Save, Replace, Update, SaveChanges)
    def _touch_updated_at(self) -> None:
        self.updatedAt = _now_utc()

    class Settings:
        name = "configs"
