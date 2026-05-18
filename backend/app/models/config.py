from datetime import datetime

from beanie import Document
from pydantic import BaseModel, Field


class UserSettings(BaseModel):
    theme: str = "auto"
    fontSize: str = "md"
    language: str = "es"


class Config(Document):
    passwordHash: str
    settings: UserSettings = Field(default_factory=UserSettings)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "configs"
