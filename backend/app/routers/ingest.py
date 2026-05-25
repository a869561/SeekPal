import asyncio
import json
import time

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.deps.auth import require_auth
from app.services import scanner_service
from app.services.scanner_service import ingest_source

router = APIRouter(prefix="/api/sources", tags=["ingest"])

# Strong references so tasks aren't GC'd mid-run
_running: set[asyncio.Task] = set()
# Per-source active task and SSE queue
_tasks: dict[str, asyncio.Task] = {}
_queues: dict[str, asyncio.Queue] = {}


def cancel_ingest_for_source(sid: str) -> None:
    """Cancel any running ingestion for this source and clean up state.

    Publica para que sources_service.remove_source() la invoque al borrar la
    fuente — asi la task de ingesta termina antes de que delete_by_source borre
    los chunks de Qdrant (evita chunks huerfanos por race condition)."""
    old = _tasks.pop(sid, None)
    if old and not old.done():
        old.cancel()
    _queues.pop(sid, None)
    scanner_service.resume_ingest(sid)  # clear any pause so the task can exit
    scanner_service.cleanup_ingest(sid)


# Alias interno (compat con el handler de ingest)
_cancel_existing = cancel_ingest_for_source


@router.post("/{source_id}/ingest", dependencies=[Depends(require_auth)])
async def ingest(source_id: PydanticObjectId, request: Request):
    sid = str(source_id)
    _cancel_existing(sid)

    queue: asyncio.Queue[dict] = asyncio.Queue()
    _queues[sid] = queue

    async def on_progress(current: int, total: int, file: str) -> None:
        # Scanner usa total<0 + sentinel en `file` para distinguir fases RAG:
        #   __extract__:<name>          -> progreso de extraccion+chunking
        #   __embedding__               -> marca arranque de la fase embedding
        #   __embed_progress__:<c>/<t>  -> progreso de embedding por lote
        #   (resto)                     -> progreso de indexado (Qdrant + Mongo)
        if total >= 0:
            await queue.put({"type": "progress", "current": current, "total": total, "file": file})
            return
        real_total = -total
        if file == "__embedding__":
            await queue.put({"type": "embedding_start", "total": real_total})
        elif file.startswith("__extract__:"):
            await queue.put({"type": "extracting_progress", "current": current,
                             "total": real_total, "file": file[len("__extract__:"):]})
        elif file.startswith("__embed_progress__:"):
            c, t = file[len("__embed_progress__:"):].split("/")
            await queue.put({"type": "embedding_progress", "current": int(c), "total": int(t)})
        else:
            await queue.put({"type": "indexing_progress", "current": current,
                             "total": real_total, "file": file})

    async def runner() -> None:
        try:
            await queue.put({"type": "scanning"})
            await ingest_source(source_id, on_progress)
            await queue.put({"type": "done"})
        except asyncio.CancelledError:
            await queue.put({"type": "cancelled"})
        except Exception as exc:
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put({"type": "__end__"})
            _tasks.pop(sid, None)
            _queues.pop(sid, None)

    task = asyncio.create_task(runner())
    _running.add(task)
    task.add_done_callback(_running.discard)
    _tasks[sid] = task

    _HEARTBEAT_INTERVAL = 15.0

    async def event_stream():
        last_yield = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                if time.monotonic() - last_yield >= _HEARTBEAT_INTERVAL:
                    last_yield = time.monotonic()
                    yield {"event": "ping", "data": ""}
                continue
            if event.get("type") == "__end__":
                return
            last_yield = time.monotonic()
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_stream())


@router.post("/{source_id}/ingest/pause", dependencies=[Depends(require_auth)])
async def pause_ingest(source_id: PydanticObjectId):
    sid = str(source_id)
    if sid not in _tasks or _tasks[sid].done():
        raise HTTPException(status_code=404, detail="No hay ingesta activa")
    scanner_service.pause_ingest(sid)
    if sid in _queues:
        await _queues[sid].put({"type": "paused"})
    return {"success": True}


@router.post("/{source_id}/ingest/resume", dependencies=[Depends(require_auth)])
async def resume_ingest(source_id: PydanticObjectId):
    sid = str(source_id)
    if sid not in _tasks or _tasks[sid].done():
        raise HTTPException(status_code=404, detail="No hay ingesta activa")
    scanner_service.resume_ingest(sid)
    if sid in _queues:
        await _queues[sid].put({"type": "resumed"})
    return {"success": True}


@router.post("/{source_id}/ingest/cancel", dependencies=[Depends(require_auth)])
async def cancel_ingest(source_id: PydanticObjectId):
    _cancel_existing(str(source_id))
    return {"success": True}
