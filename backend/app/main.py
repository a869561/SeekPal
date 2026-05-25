"""Punto de entrada de la aplicación SeekPal (FastAPI).

Estructura MVC:
- core/        infraestructura compartida (config, DB, seguridad, respuestas)
- models/      documentos persistentes (Beanie ODM sobre Motor)
- schemas/    DTOs de entrada/salida (Pydantic)
- routers/    endpoints HTTP (capa de presentación)
- services/   lógica de negocio (capa de aplicación)
- utils/      utilidades transversales sin estado
- deps/       dependencias inyectables de FastAPI (auth, etc.)
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import connect_database, disconnect_database
from app.routers import (
    ask as ask_router,
    auth as auth_router,
    health as health_router,
    ingest as ingest_router,
    search as search_router,
    settings as settings_router,
    sources as sources_router,
    stats as stats_router,
    system as system_router,
)
from app.services import watcher_service


async def _cleanup_orphans() -> None:
    """Elimina FileDocs cuya Source ya no existe (race condition al borrar fuentes)."""
    from app.core.database import get_vector_service
    from app.models.file import FileDoc
    from app.models.source import Source

    source_ids = {str(s.id) for s in await Source.find().to_list()}
    all_files = await FileDoc.find().to_list()
    orphans = [f for f in all_files if str(f.sourceId) not in source_ids]
    if not orphans:
        return
    vs = get_vector_service()
    for f in orphans:
        try:
            await asyncio.to_thread(vs.delete_by_file, str(f.id))
        except Exception:
            pass
        await f.delete()
    print(f"[seekpal] Limpiados {len(orphans)} ficheros huérfanos.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    qdrant_path = await connect_database()
    print(f"[seekpal] MongoDB conectado: {settings.mongo_uri}/{settings.mongo_db}")
    print(f"[seekpal] Qdrant inicializado en: {qdrant_path}")
    await _cleanup_orphans()
    await watcher_service.init_watchers(asyncio.get_running_loop())
    try:
        yield
    finally:
        watcher_service.stop_all()
        await disconnect_database()


app = FastAPI(
    title="SeekPal API",
    version="0.2.0",
    description="Buscador inteligente de repositorios documentales.",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail or "Error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "Datos inválidos", "errors": exc.errors()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    print(f"[seekpal] Unhandled error: {exc!r}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Error interno del servidor"},
    )


app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(sources_router.router)
app.include_router(ingest_router.router)
app.include_router(stats_router.router)
app.include_router(search_router.router)
app.include_router(settings_router.router)
app.include_router(system_router.router)
app.include_router(ask_router.router)


@app.get("/", include_in_schema=False)
async def root():
    return {"name": "SeekPal API", "version": app.version, "docs": "/docs"}
