import asyncio
import json
import time

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.deps.auth import require_auth
from app.core.responses import ok
from app.models.source import Source
from app.services import scanner_service
from app.services.scanner_service import ingest_source

router = APIRouter(prefix="/api/sources", tags=["ingest"])

# Strong references so tasks aren't GC'd mid-run
_running: set[asyncio.Task] = set()
# Per-source active task and SSE queue
_tasks: dict[str, asyncio.Task] = {}
_queues: dict[str, asyncio.Queue] = {}
# Snapshot de progreso por fuente, INDEPENDIENTE de la conexion SSE. La tarea de
# ingesta sigue viva si el cliente se desconecta (cambio de pestana / F5), asi
# que seguimos actualizando este snapshot. Al reconectar, el cliente recibe 409
# en el POST y sondea GET /ingest/progress para recuperar el progreso real en
# vez de quedarse con una barra indeterminada.
_progress: dict[str, dict] = {}


def _empty_snapshot() -> dict:
    return {
        "active": True,
        "phase": "scanning",
        "paused": False,
        "error": None,
        "scan":    {"current": 0, "total": 0, "file": ""},
        "extract": {"current": 0, "total": 0, "file": ""},
        "embed":   {"current": 0, "total": 0},
        "index":   {"current": 0, "total": 0, "file": ""},
    }


def _apply_event(snap: dict, event: dict) -> dict:
    """Aplica un evento SSE al snapshot consolidado (funcion pura sobre `snap`).

    Refleja el mismo mapeo que el manejador de eventos del frontend, pero del
    lado servidor, para que un cliente que reconecta pueda reconstruir el estado
    sin haber visto los eventos previos."""
    etype = event.get("type")
    if etype == "scanning":
        snap["phase"] = "scanning"
    elif etype == "progress":
        snap["scan"] = {"current": event["current"], "total": event["total"], "file": event.get("file", "")}
    elif etype == "extracting_progress":
        snap["phase"] = "extracting"
        snap["extract"] = {"current": event["current"], "total": event["total"], "file": event.get("file", "")}
    elif etype == "embedding_start":
        snap["phase"] = "embedding"
        snap["extract"] = {**snap["extract"], "total": event["total"]}
        snap["embed"] = {"current": 0, "total": 0}
    elif etype == "embedding_progress":
        snap["embed"] = {"current": event["current"], "total": event["total"]}
    elif etype == "indexing_progress":
        snap["phase"] = "indexing"
        snap["index"] = {"current": event["current"], "total": event["total"], "file": event.get("file", "")}
    elif etype == "paused":
        snap["paused"] = True
    elif etype == "resumed":
        snap["paused"] = False
    elif etype == "cancelled":
        snap["phase"] = "cancelled"
        snap["active"] = False
    elif etype == "done":
        snap["phase"] = "done"
        snap["active"] = False
    elif etype == "error":
        snap["phase"] = "error"
        snap["active"] = False
        snap["error"] = event.get("message")
    return snap


def _record_progress(sid: str, event: dict) -> None:
    snap = _progress.get(sid) or _empty_snapshot()
    _progress[sid] = _apply_event(snap, event)


def cancel_ingest_for_source(sid: str) -> None:
    """Cancel any running ingestion for this source and clean up state.

    Publica para que sources_service.remove_source() la invoque al borrar la
    fuente — asi la task de ingesta termina antes de que delete_by_source borre
    los chunks de Qdrant (evita chunks huerfanos por race condition)."""
    old = _tasks.pop(sid, None)
    if old and not old.done():
        old.cancel()
    _queues.pop(sid, None)
    _progress.pop(sid, None)
    scanner_service.resume_ingest(sid)  # clear any pause so the task can exit
    scanner_service.cleanup_ingest(sid)


# Alias interno (compat con el handler de ingest)
_cancel_existing = cancel_ingest_for_source


@router.post("/{source_id}/ingest", dependencies=[Depends(require_auth)])
async def ingest(source_id: PydanticObjectId, request: Request):
    sid = str(source_id)

    # Si ya hay una ingesta activa para esta fuente, rechazar en lugar de
    # cancelarla: el frontend puede haberse desconectado (navegación) y estar
    # reconectando, no queremos perder el progreso.
    if sid in _tasks and not _tasks[sid].done():
        raise HTTPException(status_code=409, detail="Ingesta ya en progreso")

    _cancel_existing(sid)

    queue: asyncio.Queue[dict] = asyncio.Queue()
    _queues[sid] = queue
    _progress[sid] = _empty_snapshot()

    async def emit(event: dict) -> None:
        # Toda emision pasa por aqui: actualiza el snapshot persistente (para
        # que un cliente que reconecta recupere el progreso real) y encola el
        # evento para el stream SSE activo. El snapshot NO incluye el sentinel
        # interno __end__.
        if event.get("type") != "__end__":
            _record_progress(sid, event)
        await queue.put(event)

    async def on_progress(current: int, total: int, file: str) -> None:
        # Scanner usa total<0 + sentinel en `file` para distinguir fases RAG:
        #   __extract__:<name>          -> progreso de extraccion+chunking
        #   __embedding__               -> marca arranque de la fase embedding
        #   __embed_progress__:<c>/<t>  -> progreso de embedding por lote
        #   (resto)                     -> progreso de indexado (Qdrant + Mongo)
        if total >= 0:
            await emit({"type": "progress", "current": current, "total": total, "file": file})
            return
        real_total = -total
        if file == "__embedding__":
            await emit({"type": "embedding_start", "total": real_total})
        elif file.startswith("__extract__:"):
            await emit({"type": "extracting_progress", "current": current,
                        "total": real_total, "file": file[len("__extract__:"):]})
        elif file.startswith("__embed_progress__:"):
            c, t = file[len("__embed_progress__:"):].split("/")
            await emit({"type": "embedding_progress", "current": int(c), "total": int(t)})
        else:
            await emit({"type": "indexing_progress", "current": current,
                        "total": real_total, "file": file})

    async def runner() -> None:
        try:
            await emit({"type": "scanning"})
            await ingest_source(source_id, on_progress)
            await emit({"type": "done"})
        except asyncio.CancelledError:
            await emit({"type": "cancelled"})
        except Exception as exc:
            await emit({"type": "error", "message": str(exc)})
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


@router.get("/{source_id}/ingest/progress", dependencies=[Depends(require_auth)])
async def get_ingest_progress(source_id: PydanticObjectId):
    """Snapshot del progreso de la ingesta en curso, independiente del SSE.

    Lo usa el cliente que reconecta (recibio 409 en el POST porque la tarea
    sigue viva) para reconstruir las barras reales en vez de quedarse con una
    barra indeterminada. `active=false` si no hay tarea viva."""
    sid = str(source_id)
    snap = _progress.get(sid)
    if snap is None:
        return ok({"active": False})
    active = sid in _tasks and not _tasks[sid].done()
    return ok({**snap, "active": active})


@router.post("/{source_id}/ingest/pause", dependencies=[Depends(require_auth)])
async def pause_ingest(source_id: PydanticObjectId):
    sid = str(source_id)
    if sid not in _tasks or _tasks[sid].done():
        raise HTTPException(status_code=404, detail="No hay ingesta activa")
    scanner_service.pause_ingest(sid)
    _record_progress(sid, {"type": "paused"})
    if sid in _queues:
        await _queues[sid].put({"type": "paused"})
    return {"success": True}


@router.post("/{source_id}/ingest/resume", dependencies=[Depends(require_auth)])
async def resume_ingest(source_id: PydanticObjectId):
    sid = str(source_id)
    if sid not in _tasks or _tasks[sid].done():
        raise HTTPException(status_code=404, detail="No hay ingesta activa")
    scanner_service.resume_ingest(sid)
    _record_progress(sid, {"type": "resumed"})
    if sid in _queues:
        await _queues[sid].put({"type": "resumed"})
    return {"success": True}


@router.post("/{source_id}/ingest/cancel", dependencies=[Depends(require_auth)])
async def cancel_ingest(source_id: PydanticObjectId):
    _cancel_existing(str(source_id))
    # El task cancelado lanza CancelledError (BaseException, no Exception), asi que
    # ingest_source no llega a actualizar el estado y la fuente quedaria colgada en
    # "scanning": el frontend la reanudaria sola tras F5. La marcamos en estado
    # terminal aqui. Solo si sigue en "scanning" para no pisar un "done"/"error"
    # que el task haya escrito justo antes de la cancelacion.
    src = await Source.get(source_id)
    if src is not None and src.status == "scanning":
        src.status = "idle"
        await src.save()
    return {"success": True}
