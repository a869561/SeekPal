"""Generación de respuestas streaming via Ollama (Llama 3.2 3B).

build_prompt usa str.replace() con placeholders únicos (<<<...>>>) para evitar
conflictos con llaves literales en el texto de los chunks.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from ollama import AsyncClient

from app.services.rag.types import RetrievedChunk


_TEMPLATE_PATH = Path(__file__).parent / "templates" / "qa_prompt.txt"
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n".join(
        f"[{i + 1}] (chunk_id={c.chunk_id}) {c.text}"
        for i, c in enumerate(chunks)
    )
    return _TEMPLATE.replace("<<<CONTEXT>>>", context).replace("<<<QUESTION>>>", question)


class GenerationService:
    def __init__(self, base_url: str, model: str):
        self._client = AsyncClient(host=base_url, timeout=120.0)
        self._model = model

    async def generate_stream(
        self, question: str, chunks: list[RetrievedChunk]
    ) -> AsyncGenerator[str, None]:
        prompt = build_prompt(question, chunks)
        messages = [{"role": "user", "content": prompt}]
        async for part in await self._client.chat(
            model=self._model,
            messages=messages,
            stream=True,
            options={"temperature": 0.2, "num_ctx": 8192},
        ):
            yield part.message.content or ""
            if part.done:
                break

    async def close(self) -> None:
        await self._client._client.aclose()
