from pathlib import Path

from beanie import PydanticObjectId

from app.core.responses import APIError
from app.models.file import FileDoc
from app.models.source import Source


async def list_sources() -> list[Source]:
    return await Source.find().sort("-createdAt").to_list()


async def add_source(name: str, dir_path: str) -> Source:
    p = Path(dir_path)
    if not p.exists() or not p.is_dir():
        raise APIError("Directorio no encontrado o sin acceso", status_code=400)

    existing = await Source.find_one(Source.path == str(p))
    if existing:
        raise APIError("Ya existe una fuente con esa ruta", status_code=409)

    source = Source(name=name, path=str(p))
    await source.insert()
    return source


async def remove_source(source_id: PydanticObjectId) -> Source:
    source = await Source.get(source_id)
    if source is None:
        raise APIError("Fuente no encontrada", status_code=404)
    await FileDoc.find(FileDoc.sourceId == source_id).delete()
    await source.delete()
    return source


async def toggle_auto_index(source_id: PydanticObjectId) -> Source:
    source = await Source.get(source_id)
    if source is None:
        raise APIError("Fuente no encontrada", status_code=404)
    source.autoIndex = not source.autoIndex
    await source.save()
    return source
