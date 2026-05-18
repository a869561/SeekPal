from beanie import PydanticObjectId
from fastapi import APIRouter, Depends

from app.core.responses import created, ok
from app.deps.auth import require_auth
from app.schemas.source import AddSourceRequest
from app.services import sources_service
from app.utils.serialization import serialize, serialize_many

router = APIRouter(prefix="/api/sources", tags=["sources"], dependencies=[Depends(require_auth)])


@router.get("")
async def list_sources():
    items = await sources_service.list_sources()
    return ok(serialize_many(items))


@router.post("")
async def add_source(body: AddSourceRequest):
    source = await sources_service.add_source(body.name, body.path)
    return created(serialize(source), "Fuente añadida")


@router.delete("/{source_id}")
async def remove_source(source_id: PydanticObjectId):
    await sources_service.remove_source(source_id)
    return ok(None, "Fuente eliminada")


@router.patch("/{source_id}/auto-index")
async def toggle_auto_index(source_id: PydanticObjectId):
    from app.services import watcher_service

    source = await sources_service.toggle_auto_index(source_id)
    if source.autoIndex:
        watcher_service.start(str(source.id), source.path)
    else:
        watcher_service.stop(str(source.id))
    return ok(serialize(source))
