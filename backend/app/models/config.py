from datetime import UTC, datetime

from beanie import Document
from pydantic import BaseModel, Field


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
    whisperModel: str = "small"  # tiny | base | small | medium

    # Multimedia
    indexMultimedia: bool = True       # master switch para audio/imagen/video
    videoFrameInterval: int = 30       # segundos entre frames muestreados
    videoMaxFrames: int = 20           # tope por video para acotar coste


class Config(Document):
    passwordHash: str
    settings: UserSettings = Field(default_factory=UserSettings)
    createdAt: datetime = Field(default_factory=_now_utc)
    updatedAt: datetime = Field(default_factory=_now_utc)

    class Settings:
        name = "configs"
