from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models.config import Config
from app.models.source import Source
from app.models.file import FileDoc


_client: AsyncIOMotorClient | None = None


async def connect_database() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)
    db = _client[settings.mongo_db]
    await init_beanie(database=db, document_models=[Config, Source, FileDoc])


async def disconnect_database() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def is_connected() -> bool:
    return _client is not None
