import asyncio
import json

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.deps.auth import require_auth
from app.services.scanner_service import ingest_source

router = APIRouter(prefix="/api/sources", tags=["ingest"])


@router.post("/{source_id}/ingest", dependencies=[Depends(require_auth)])
async def ingest(source_id: PydanticObjectId, request: Request):
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def on_progress(current: int, total: int, file: str) -> None:
        await queue.put({"type": "progress", "current": current, "total": total, "file": file})

    async def runner() -> None:
        try:
            await queue.put({"type": "scanning"})
            await ingest_source(source_id, on_progress)
            await queue.put({"type": "done"})
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put({"type": "__end__"})

    task = asyncio.create_task(runner())

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    task.cancel()
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if event.get("type") == "__end__":
                    return
                yield {"data": json.dumps(event)}
        finally:
            if not task.done():
                task.cancel()

    return EventSourceResponse(event_stream())
