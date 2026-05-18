"""Auto-reindexación de fuentes con `watchdog`.

Cada fuente con `autoIndex=True` mantiene un Observer escuchando cambios en su
directorio raíz (recursivo). Los eventos se debounce-ean 10 s para evitar
ráfagas durante operaciones en cadena (descomprimir, mover, etc.).
"""

import asyncio
import threading
from typing import Optional

from beanie import PydanticObjectId
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.models.source import Source
from app.services.scanner_service import ingest_source


DEBOUNCE_SECONDS = 10.0

_observers: dict[str, Observer] = {}
_timers: dict[str, threading.Timer] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None


async def _noop_progress(_c: int, _t: int, _f: str) -> None:
    return None


def _schedule_reingest(source_id: str) -> None:
    existing = _timers.pop(source_id, None)
    if existing is not None:
        existing.cancel()

    def fire() -> None:
        _timers.pop(source_id, None)
        if _loop is None or _loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(_reingest(source_id), _loop)

    timer = threading.Timer(DEBOUNCE_SECONDS, fire)
    timer.daemon = True
    timer.start()
    _timers[source_id] = timer


async def _reingest(source_id: str) -> None:
    try:
        await ingest_source(PydanticObjectId(source_id), _noop_progress)
        print(f"[watcher] auto-reindexed source {source_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"[watcher] error re-indexing {source_id}: {exc}")


class _Handler(FileSystemEventHandler):
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def _trigger(self) -> None:
        _schedule_reingest(self.source_id)

    def on_any_event(self, event):
        if event.is_directory:
            return
        self._trigger()


def start(source_id: str, dir_path: str) -> None:
    if source_id in _observers:
        return
    try:
        observer = Observer()
        observer.schedule(_Handler(source_id), dir_path, recursive=True)
        observer.start()
        _observers[source_id] = observer
        print(f"[watcher] watching {dir_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"[watcher] cannot watch {dir_path}: {exc}")


def stop(source_id: str) -> None:
    timer = _timers.pop(source_id, None)
    if timer is not None:
        timer.cancel()
    observer = _observers.pop(source_id, None)
    if observer is not None:
        observer.stop()
        observer.join(timeout=2.0)


def stop_all() -> None:
    for sid in list(_observers.keys()):
        stop(sid)


async def init_watchers(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop
    sources = await Source.find(Source.autoIndex == True).to_list()  # noqa: E712
    for s in sources:
        start(str(s.id), s.path)
    print(f"[watcher] {len(sources)} watcher(s) inicializados")
