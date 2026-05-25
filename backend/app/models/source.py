from datetime import UTC, datetime
from typing import Literal

import pymongo
from beanie import Document
from pydantic import Field


SourceStatus = Literal["idle", "scanning", "done", "error"]


def _now_utc() -> datetime:
    return datetime.now(UTC)


class Source(Document):
    name: str
    path: str
    status: SourceStatus = "idle"
    lastIngested: datetime | None = None
    fileCount: int = 0
    autoIndex: bool = False
    createdAt: datetime = Field(default_factory=_now_utc)
    updatedAt: datetime = Field(default_factory=_now_utc)

    class Settings:
        name = "sources"
        indexes = [
            pymongo.IndexModel("path", unique=True),
        ]
