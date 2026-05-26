"""Auto-reindexación de fuentes con `watchdog`.

Cada fuente con `autoIndex=True` mantiene un _handler_ escuchando cambios en
su directorio raiz (recursivo). Todos los handlers comparten un UNICO Observer
en lugar de uno por fuente — esto reduce la presion de threads y el consumo de
inotify/handles de fichero en sistemas con muchas fuentes activas.

Los eventos se debounce-ean 10 s para evitar rafagas durante operaciones en
cadena (descomprimir, mover, etc.).

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

# --------------------------------------------------------------------------
# Estado del modulo
# --------------------------------------------------------------------------

# Observer compartido — se crea una sola vez en init_watchers()
_observer: Optional[Observer] = None
_observer_lock = threading.Lock()

# Mapea source_id → watch token de watchdog (para poder hacer unschedule)
_watches: dict[str, object] = {}

# Timers de debounce por source_id
_timers: dict[str, threading.Timer] = {}

# Event loop del proceso principal (necesario para run_coroutine_threadsafe)
_loop: Optional[asyncio.AbstractEventLoop] = None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Handler por fuente
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# API publica
# --------------------------------------------------------------------------

def _ensure_observer() -> Observer:
    """Crea e inicia el Observer compartido si aun no existe."""
    global _observer
    with _observer_lock:
        if _observer is None or not _observer.is_alive():
            _observer = Observer()
            _observer.start()
            logger.debug("Observer compartido iniciado")
    return _observer


def start(source_id: str, dir_path: str) -> None:
    """Comienza a vigilar dir_path para la fuente source_id.

    Usa el Observer compartido — no crea un thread nuevo por fuente.
    Si la fuente ya esta siendo vigilada, es un no-op.
    """
    if source_id in _watches:
        return
    try:
        observer = _ensure_observer()
        watch = observer.schedule(_Handler(source_id), dir_path, recursive=True)
        _watches[source_id] = watch
        logger.info("watching %s (source=%s)", dir_path, source_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("cannot watch %s: %s", dir_path, exc)


def stop(source_id: str) -> None:
    """Deja de vigilar la fuente source_id."""
    # Cancelar timer de debounce pendiente
    timer = _timers.pop(source_id, None)
    if timer is not None:
        timer.cancel()

    # Desregistrar handler del Observer compartido
    watch = _watches.pop(source_id, None)
    if watch is not None and _observer is not None:
        try:
            _observer.unschedule(watch)
            logger.debug("stopped watching source=%s", source_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("error unscheduling source %s: %s", source_id, exc)


def stop_all() -> None:
    """Para todos los watchers y detiene el Observer compartido."""
    global _observer
    for sid in list(_watches.keys()):
        stop(sid)
    with _observer_lock:
        if _observer is not None:
            try:
                _observer.stop()
                _observer.join(timeout=2.0)
            except Exception:
                pass
            _observer = None
    logger.info("Observer compartido detenido")


async def init_watchers(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop
    sources = await Source.find(Source.autoIndex == True).to_list()  # noqa: E712
    for s in sources:
        start(str(s.id), s.path)
    logger.info("%d watcher(s) inicializados (Observer compartido)", len(sources))
