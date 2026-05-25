from datetime import UTC, datetime
from typing import Literal

from beanie import Document, before_event
from beanie.odm.actions import Replace, Save, SaveChanges, Update
from pydantic import BaseModel, Field


WhisperModel = Literal["tiny", "base", "small", "medium", "large"]


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

    # Multimedia
    indexMultimedia: bool = True       # master switch para audio/imagen/video
    videoFrameInterval: int = Field(default=30, ge=1, le=600)
    videoMaxFrames: int = Field(default=20, ge=1, le=500)


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
