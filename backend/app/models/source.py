from datetime import UTC, datetime
from typing import Literal

import pymongo
from beanie import Document, before_event
from beanie.odm.actions import Replace, Save, SaveChanges, Update
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
    indexedCount: int = 0
    skippedCount: int = 0
    failedCount: int = 0
    autoIndex: bool = False
    createdAt: datetime = Field(default_factory=_now_utc)
    updatedAt: datetime = Field(default_factory=_now_utc)

    @before_event(Save, Replace, Update, SaveChanges)
    def _touch_updated_at(self) -> None:
        self.updatedAt = _now_utc()

    class Settings:
        name = "sources"
        indexes = [
            pymongo.IndexModel("path", unique=True),
        ]
