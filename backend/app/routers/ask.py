import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from ollama import AsyncClient
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.database import get_generation_service, get_retrieval_service, get_vector_service, is_connected
from app.core.responses import RagErrorCode, ok
from app.deps.auth import require_auth
from app.schemas.ask import AskRequest, Citation

logger = logging.getLogger("seekpal.ask")


# Cliente HTTP de health: reusable y compartido — antes se creaba uno por
# llamada y nunca se cerraba (httpx conexiones se acumulaban en el pool).
_health_client: AsyncClient | None = None


def _get_health_client() -> AsyncClient:
    global _health_client
    if _health_client is None:
        _health_client = AsyncClient(host=settings.ollama_url, timeout=10.0)
    return _health_client

router = APIRouter(prefix="/api/ask", tags=["ask"], dependencies=[Depends(require_auth)])


@router.post("")
async def ask(body: AskRequest, request: Request):
    async def event_stream():
        try:
            retrieval = get_retrieval_service()
            generation = get_generation_service()

            # Multi-query expansion: pide al LLM N reformulaciones de la pregunta
            # para cubrir sinonimos y angulos distintos antes del retrieval.
            # Si falla o esta deshabilitado, cae de forma graceful a una sola query.
            if settings.rag_multi_query_enabled:
                try:
                    questions = await generation.expand_query(
                        body.question, n=settings.rag_multi_query_n
                    )
                    logger.debug(
                        "Multi-query: %d variantes para %r",
                        len(questions),
                        body.question[:60],
                    )
                    chunks = await retrieval.retrieve_multi(
                        questions=questions,
                        top_k=body.top_k,
                        source_id=body.source_id,
                        categories=body.categories,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Multi-query fallo, fallback a single-query: %s", exc)
                    chunks = await retrieval.retrieve(
                        question=body.question,
                        top_k=body.top_k,
                        source_id=body.source_id,
                        categories=body.categories,
                    )
            else:
                chunks = await retrieval.retrieve(
                    question=body.question,
                    top_k=body.top_k,
                    source_id=body.source_id,
                    categories=body.categories,
                )

            citations = [
                Citation(
                    chunk_id=c.chunk_id,
                    file_id=c.file_id,
                    file_name=c.file_name,
                    page=c.page,
                    snippet=c.text[:200] + ("..." if len(c.text) > 200 else ""),
                    score=c.score,
                ).model_dump()
                for c in chunks
            ]
            yield {"data": json.dumps({"type": "retrieved", "citations": citations})}

            if not chunks:
                yield {"data": json.dumps({"type": "token", "text": "No tengo información suficiente en los documentos indexados."})}
                yield {"data": json.dumps({"type": "done"})}
                return

            async for event_type, text in generation.generate_stream(body.question, chunks):
                if await request.is_disconnected():
                    return
                if text:
                    # event_type es "token" (respuesta) o "thinking" (razonamiento)
                    yield {"data": json.dumps({"type": event_type, "text": text})}

            yield {"data": json.dumps({"type": "done"})}

        except Exception as exc:
            yield {"data": json.dumps({
                "type": "error",
                "code": RagErrorCode.GENERATION_FAILED.value,
                # str(exc) de un httpx.ReadTimeout viene vacío; garantizar mensaje.
                "message": str(exc) or f"{type(exc).__name__} (¿modelo LLM demasiado pesado para este hardware?)",
            })}

    return EventSourceResponse(event_stream())


@router.get("/config")
async def ask_config():
    """Expone los parámetros RAG que el frontend necesita conocer."""
    return ok({"top_k": settings.rag_top_k})


@router.get("/health")
async def ask_health():
    client = _get_health_client()

    try:
        resp = await client.list()
        ollama_info = {"status": "up", "models": [m.model for m in resp.models]}
    except Exception as exc:
        ollama_info = {"status": "down", "error": str(exc)}

    try:
        vector = get_vector_service()
        count = await asyncio.to_thread(vector.count)
        qdrant_info = {"status": "up", "vectors_count": count}
    except Exception as exc:
        qdrant_info = {"status": "down", "error": str(exc)}

    mongo_info = {"status": "up" if is_connected() else "down"}

    return ok({"ollama": ollama_info, "qdrant": qdrant_info, "mongo": mongo_info})
