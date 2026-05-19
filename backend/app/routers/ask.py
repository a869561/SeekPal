import asyncio
import json

from fastapi import APIRouter, Depends, Request
from ollama import AsyncClient
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.database import get_generation_service, get_retrieval_service, get_vector_service, is_connected
from app.core.responses import RagErrorCode, ok
from app.deps.auth import require_auth
from app.schemas.ask import AskRequest, Citation

router = APIRouter(prefix="/api/ask", tags=["ask"], dependencies=[Depends(require_auth)])


@router.post("")
async def ask(body: AskRequest, request: Request):
    async def event_stream():
        try:
            retrieval = get_retrieval_service()
            generation = get_generation_service()

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

            async for token in generation.generate_stream(body.question, chunks):
                if await request.is_disconnected():
                    return
                if token:
                    yield {"data": json.dumps({"type": "token", "text": token})}

            yield {"data": json.dumps({"type": "done"})}

        except Exception as exc:
            yield {"data": json.dumps({
                "type": "error",
                "code": RagErrorCode.GENERATION_FAILED.value,
                "message": str(exc),
            })}

    return EventSourceResponse(event_stream())


@router.get("/health")
async def ask_health():
    client = AsyncClient(host=settings.ollama_url, timeout=10.0)

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
