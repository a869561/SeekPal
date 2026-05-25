"""Auto-reindexación de fuentes con `watchdog`.

Cada fuente con `autoIndex=True` mantiene un Observer escuchando cambios en su
directorio raíz (recursivo). Los eventos se debounce-ean 10 s para evitar
ráfagas durante operaciones en cadena (descomprimir, mover, etc.).

Filtros aplicados al evento crudo de watchdog:
  - Solo created/modified/deleted/moved (no opened/closed/accessed que
    disparan re-ingestas espurias al abrir un fichero para leerlo).
  - Excluye ficheros temporales (.tmp, .swp, .crdownload) y placeholders
    de Office (~$documento.docx) que aparecen y desaparecen mientras
    el usuario trabaja.
"""

import asyncio
import logging
import threading
from pathlib import PurePath
from typing import Optional

from beanie import PydanticObjectId
from watchdog.events import (
    EVENT_TYPE_CREATED,
    EVENT_TYPE_DELETED,
    EVENT_TYPE_MODIFIED,
    EVENT_TYPE_MOVED,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from app.models.source import Source
from app.services.scanner_service import ingest_source

logger = logging.getLogger("seekpal.watcher")


DEBOUNCE_SECONDS = 10.0

# Eventos que cuentan como cambio real del contenido indexable.
_REAL_CHANGE_EVENTS = frozenset({
    EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED,
    EVENT_TYPE_DELETED, EVENT_TYPE_MOVED,
})

# Extensiones y prefijos tipicos de ficheros transitorios que no deben
# disparar re-ingestas (editores, descargas en curso, lockfiles de Office).
_TEMP_SUFFIXES = frozenset({
    ".tmp", ".temp", ".swp", ".swx", ".swo", ".part", ".crdownload",
    ".bak", ".orig",
})
_TEMP_PREFIXES = ("~$", ".~lock.", ".#")

_observers: dict[str, Observer] = {}
_timers: dict[str, threading.Timer] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None


def _is_transient(path: str) -> bool:
    """True si el path corresponde a un fichero transitorio que debe ignorarse."""
    p = PurePath(path)
    name = p.name
    if name.startswith(_TEMP_PREFIXES):
        return True
    if p.suffix.lower() in _TEMP_SUFFIXES:
        return True
    return False


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
        logger.info("auto-reindexed source %s", source_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("error re-indexing %s: %s", source_id, exc)


class _Handler(FileSystemEventHandler):
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def _trigger(self) -> None:
        _schedule_reingest(self.source_id)

    def on_any_event(self, event):
        if event.is_directory:
            return
        # Filtrar eventos espurios: solo reaccionar a cambios reales del
        # contenido (created/modified/deleted/moved), no a accesos.
        if event.event_type not in _REAL_CHANGE_EVENTS:
            return
        # Ignorar transitorios (Office lock files, .tmp, .crdownload, etc.)
        path = getattr(event, "dest_path", None) or event.src_path
        if _is_transient(path):
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
        logger.info("watching %s", dir_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("cannot watch %s: %s", dir_path, exc)


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
    logger.info("%d watcher(s) inicializados", len(sources))
