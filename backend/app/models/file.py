from datetime import datetime
from typing import Literal

import pymongo
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


FileCategory = Literal["text", "document", "image", "audio", "video", "other"]


class FileMetadata(BaseModel):
    # text / document
    wordCount: int | None = None
    charCount: int | None = None
    # image
    width: int | None = None
    height: int | None = None
    ppi: float | None = None
    # audio
    duration: int | None = None
    bitrate: int | None = None
    # video
    fps: float | None = None


class FileDoc(Document):
    sourceId: PydanticObjectId
    name: str
    path: str
    extension: str = ""
    mimeType: str = "application/octet-stream"
    category: FileCategory = "other"
    size: int = 0
    createdAt: datetime | None = None
    modifiedAt: datetime | None = None
    metadata: FileMetadata = Field(default_factory=FileMetadata)

    class Settings:
        name = "files"
        indexes = [
            pymongo.IndexModel([("sourceId", pymongo.ASCENDING)]),
            pymongo.IndexModel(
                [("sourceId", pymongo.ASCENDING), ("path", pymongo.ASCENDING)],
                unique=True,
            ),
        ]
