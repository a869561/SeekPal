"""Generación de respuestas streaming via Ollama.

build_prompt usa str.replace() con placeholders únicos (<<<...>>>) para evitar
conflictos con llaves literales en el texto de los chunks.

GenerationService tambien expone expand_query() para multi-query retrieval:
pide al LLM N reformulaciones de la pregunta original (sinonimos, distintos
angulos) que se usan para sobre-cubrir el espacio semantico antes del retrieval.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from pathlib import Path

from ollama import AsyncClient

from app.services.rag.types import RetrievedChunk

logger = logging.getLogger("seekpal.generation")


_TEMPLATE_PATH = Path(__file__).parent / "templates" / "qa_prompt.txt"
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")

_EXPAND_PROMPT = """Eres un asistente que ayuda a buscar informacion en una base de documentos.

Tu tarea: dada una pregunta del usuario, generar {n} reformulaciones distintas
que cubran sinonimos, terminos relacionados y angulos complementarios. Cada
reformulacion debe ser breve (una frase) y mantener el sentido original.

Devuelve SOLO las reformulaciones, una por linea, sin numeracion ni explicacion.

Pregunta: {question}

Reformulaciones:"""


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n".join(
        f"[{i + 1}] (chunk_id={c.chunk_id}) {c.text}"
        for i, c in enumerate(chunks)
    )
    return _TEMPLATE.replace("<<<CONTEXT>>>", context).replace("<<<QUESTION>>>", question)


def _clean_variant(line: str) -> str:
    """Limpia ruido tipico del LLM (numeracion, viñetas, comillas)."""
    s = line.strip()
    # Quita "1." "1)" "-" "*" "•" al inicio
    s = re.sub(r"^[\d\-\*•·]+[\.\)]?\s*", "", s)
    # Quita comillas envolventes
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'", "«"):
        s = s[1:-1].strip()
    return s


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

    async def expand_query(self, question: str, n: int = 3) -> list[str]:
        """Pide al LLM N reformulaciones de la pregunta para multi-query retrieval.

        Devuelve [question, variante1, variante2, ...]. Si el LLM falla o no
        produce nada usable, devuelve solo [question] (degradacion graceful).
        Temperatura mas alta (0.7) que en generate_stream para favorecer
        variedad lexica.
        """
        if n < 1:
            return [question]
        prompt = _EXPAND_PROMPT.format(n=n, question=question)
        try:
            resp = await self._client.chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.7, "num_ctx": 2048},
            )
            text = (resp.message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("expand_query fallo: %s", exc)
            return [question]

        # Algunos modelos thinking (Qwen3) envuelven la respuesta en <think>...</think>;
        # eliminamos esos bloques antes de parsear las variantes.
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        variants = [_clean_variant(l) for l in text.splitlines()]
        # Filtros: no vacio, distinto de la pregunta original (case-insensitive),
        # razonable de longitud (10-300 chars).
        q_lower = question.lower().strip()
        clean: list[str] = []
        seen: set[str] = {q_lower}
        for v in variants:
            v_lower = v.lower().strip()
            if not v_lower or v_lower in seen:
                continue
            if len(v) < 10 or len(v) > 300:
                continue
            clean.append(v)
            seen.add(v_lower)
            if len(clean) >= n:
                break

        return [question, *clean]

    async def close(self) -> None:
        await self._client._client.aclose()
