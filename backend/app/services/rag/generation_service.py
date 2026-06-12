"""Generación de respuestas streaming via Ollama.

build_prompt usa str.replace() con placeholders únicos (<<<...>>>) para evitar
conflictos con llaves literales en el texto de los chunks.

GenerationService expone:
  - generate_stream()  → stream de tokens con filtro de razonamiento
  - expand_query()     → reformulaciones de la pregunta para multi-query retrieval

Modo thinking (Qwen3):
  Cuando thinking=True se pasa `think: true` a Ollama, lo que hace que el LLM
  genere un bloque de razonamiento extendido antes de responder. Ese bloque
  aparece dentro de etiquetas <think>...</think> en el token stream.

  _think_filter() actua como filtro de streaming stateful:
    - Tokens dentro de <think>...</think> → yielded como ("thinking", text)
    - Tokens fuera → yielded como ("token", text)

  Con thinking=False (por defecto) el filtro igualmente limpia cualquier bloque
  <think> que el modelo emita de forma espontanea (ej. expand_query).
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
    # Incluir el nombre del fichero: a menudo lleva senal que no aparece en el
    # texto (autor, grupo, fecha, tema) y sin el el LLM no puede ligar la
    # pregunta con el documento (p.ej. "grupo 7-8" solo consta en el nombre).
    context = "\n".join(
        f"[{i + 1}] (chunk_id={c.chunk_id}, archivo={c.file_name}) {c.text}"
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


def _safe_split(text: str, tag: str) -> tuple[str, str]:
    """Divide text en (seguro_de_emitir, retener_en_buffer).

    El segmento retenido es el sufijo mas largo de text que sea un prefijo
    propio de tag (es decir, podria completarse en el siguiente token).
    Si ningun sufijo coincide, retorna ("", text) si text esta vacio o
    (text, "") si no hay coincidencia posible.
    """
    max_check = min(len(text), len(tag) - 1)
    for length in range(max_check, 0, -1):
        if tag.startswith(text[-length:]):
            return text[:-length], text[-length:]
    return text, ""


async def _think_filter(
    raw_stream: AsyncGenerator[str, None],
) -> AsyncGenerator[tuple[str, str], None]:
    """Separa tokens de respuesta de bloques <think>...</think>.

    Implementa una maquina de estados sobre el stream de tokens. No acumula
    toda la respuesta — emite tokens en cuanto puede garantizar que no son
    parte de una etiqueta incompleta.

    Yields:
      ("token", text)    → contenido de la respuesta para el usuario
      ("thinking", text) → razonamiento interno del modelo (para UI opcional)
    """
    OPEN_TAG = "<think>"
    CLOSE_TAG = "</think>"

    buffer = ""
    in_think = False

    async for chunk in raw_stream:
        buffer += chunk

        while buffer:
            tag = CLOSE_TAG if in_think else OPEN_TAG
            tag_pos = buffer.find(tag)

            if tag_pos >= 0:
                # Etiqueta encontrada: emitir contenido previo y cambiar estado
                before = buffer[:tag_pos]
                if before:
                    yield ("thinking" if in_think else "token", before)
                buffer = buffer[tag_pos + len(tag):]
                in_think = not in_think
                # Continuar el while para procesar el resto del buffer
            else:
                # Etiqueta no encontrada: emitir la parte segura, retener el resto
                safe, keep = _safe_split(buffer, tag)
                if safe:
                    yield ("thinking" if in_think else "token", safe)
                buffer = keep
                break  # Esperar mas tokens

    # Vaciar buffer restante al cerrar el stream
    if buffer:
        yield ("thinking" if in_think else "token", buffer)


class GenerationService:
    def __init__(self, base_url: str, model: str, thinking: bool = False):
        self._client = AsyncClient(host=base_url, timeout=120.0)
        self._model = model
        self._thinking = thinking
        if thinking:
            logger.info("GenerationService: modo thinking activado (Qwen3)")

    async def generate_stream(
        self, question: str, chunks: list[RetrievedChunk]
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Genera la respuesta en streaming con filtro de razonamiento.

        Yields tuplas (event_type, text):
          ("token", text)    → fragmentos de la respuesta para el usuario
          ("thinking", text) → razonamiento interno (si thinking=True o el
                               modelo lo emite espontaneamente)

        Cuando thinking=True se activa el modo de razonamiento extendido de
        Qwen3 via la opcion `think` de Ollama. El LLM genera mas contexto
        interno antes de responder, mejorando la calidad en preguntas complejas
        a costa de mayor latencia (~2-5 s extra en CPU).
        """
        options: dict = {"temperature": 0.2, "num_ctx": 8192}
        if self._thinking:
            options["think"] = True  # Activar thinking en Ollama (Qwen3/DeepSeek-R1)

        prompt = build_prompt(question, chunks)
        messages = [{"role": "user", "content": prompt}]

        async def _raw_tokens() -> AsyncGenerator[str, None]:
            async for part in await self._client.chat(
                model=self._model,
                messages=messages,
                stream=True,
                options=options,
            ):
                # Ollama >= 0.9 puede exponer el thinking en campo separado;
                # lo envolvemos en etiquetas para que _think_filter lo procese
                # de forma uniforme independientemente de la version de Ollama.
                thinking_field = getattr(part.message, "thinking", None) or ""
                if thinking_field:
                    yield f"<think>{thinking_field}</think>"
                yield part.message.content or ""
                if part.done:
                    break

        async for event in _think_filter(_raw_tokens()):
            yield event

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
