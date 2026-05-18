from fastapi import APIRouter, Depends, Query

from app.core.responses import ok
from app.deps.auth import require_auth
from app.services import stats_service
from app.utils.serialization import serialize_many

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(require_auth)])


@router.get("/summary")
async def summary():
    data = await stats_service.get_summary()
    return ok(data)


@router.get("/files")
async def files(
    sourceId: str | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    sortBy: str = "size",
    sortDir: str = "desc",
):
    result = await stats_service.get_files(
        source_id=sourceId,
        category=category,
        page=page,
        limit=limit,
        sort_by=sortBy,
        sort_dir=sortDir,
    )
    result["files"] = serialize_many(result["files"])
    return ok(result)
