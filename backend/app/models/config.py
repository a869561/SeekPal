from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field


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
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "configs"
