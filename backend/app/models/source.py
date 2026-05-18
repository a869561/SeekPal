from datetime import datetime
from typing import Literal

import pymongo
from beanie import Document
from pydantic import Field


SourceStatus = Literal["idle", "scanning", "done", "error"]


class Source(Document):
    name: str
    path: str
    status: SourceStatus = "idle"
    lastIngested: datetime | None = None
    fileCount: int = 0
    autoIndex: bool = False
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "sources"
        indexes = [
            pymongo.IndexModel("path", unique=True),
        ]
