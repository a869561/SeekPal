from fastapi import APIRouter, Depends, Query

from app.core.responses import ok
from app.deps.auth import require_auth
from app.services import search_service
from app.utils.serialization import serialize_many

router = APIRouter(prefix="/api/search", tags=["search"], dependencies=[Depends(require_auth)])


@router.get("")
async def search(
    q: str | None = None,
    category: str | None = None,
    sourceId: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=15, ge=1, le=200),
):
    result = await search_service.search(
        q=q,
        category=category,
        source_id=sourceId,
        page=page,
        limit=limit,
    )
    result["files"] = serialize_many(result["files"])
    return ok(result)
