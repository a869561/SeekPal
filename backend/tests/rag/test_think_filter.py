"""Tests para _think_filter y _safe_split (filtro de bloques <think> en streaming).

Cubre los casos edge del filtro stateful: etiquetas que llegan fragmentadas
en múltiples tokens, bloques anidados (no esperados), y buffers vacíos.
"""

from __future__ import annotations

import pytest

from app.services.rag.generation_service import _safe_split, _think_filter


# ---------------------------------------------------------------------------
# Tests para _safe_split
# ---------------------------------------------------------------------------

def test_safe_split_no_overlap():
    safe, keep = _safe_split("hello world", "<think>")
    assert safe == "hello world"
    assert keep == ""


def test_safe_split_partial_tag_at_end():
    """El sufijo '<thi' es prefijo de '<think>' → debe retenerse."""
    safe, keep = _safe_split("hello<thi", "<think>")
    assert safe == "hello"
    assert keep == "<thi"


def test_safe_split_full_tag_is_not_retained():
    """La etiqueta completa '<think>' no es un prefijo PROPIO → no se retiene."""
    safe, keep = _safe_split("hello<think>", "<think>")
    # La etiqueta completa coincide con find(), no con _safe_split
    # _safe_split solo busca prefijos propios (length < len(tag))
    assert keep == ""


def test_safe_split_empty_text():
    safe, keep = _safe_split("", "<think>")
    assert safe == ""
    assert keep == ""


def test_safe_split_single_char_prefix():
    safe, keep = _safe_split("hola<", "<think>")
    assert safe == "hola"
    assert keep == "<"


def test_safe_split_close_tag_partial():
    safe, keep = _safe_split("text</thi", "</think>")
    assert safe == "text"
    assert keep == "</thi"


# ---------------------------------------------------------------------------
# Helper para tests de _think_filter
# ---------------------------------------------------------------------------

async def _filter(tokens: list[str]) -> list[tuple[str, str]]:
    """Pasa una lista de tokens por _think_filter y devuelve todos los eventos."""
    async def _gen():
        for t in tokens:
            yield t

    events = []
    async for event in _think_filter(_gen()):
        events.append(event)
    return events


def _join_by_type(events: list[tuple[str, str]], event_type: str) -> str:
    return "".join(text for t, text in events if t == event_type)


# ---------------------------------------------------------------------------
# Tests para _think_filter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_filter_no_think_tags():
    """Sin etiquetas: todo se emite como 'token'."""
    events = await _filter(["hola ", "mundo"])
    assert all(t == "token" for t, _ in events)
    assert _join_by_type(events, "token") == "hola mundo"


@pytest.mark.asyncio
async def test_filter_think_block_in_single_token():
    """Bloque completo en un solo token."""
    events = await _filter(["<think>razonamiento</think>respuesta"])
    assert _join_by_type(events, "thinking") == "razonamiento"
    assert _join_by_type(events, "token") == "respuesta"


@pytest.mark.asyncio
async def test_filter_think_block_split_across_tokens():
    """Etiqueta <think> llega fragmentada en múltiples tokens."""
    tokens = ["pre<", "thi", "nk>", "razon</", "think>post"]
    events = await _filter(tokens)
    assert _join_by_type(events, "thinking") == "razon"
    assert _join_by_type(events, "token") == "prepost"


@pytest.mark.asyncio
async def test_filter_think_at_start():
    """Bloque thinking al inicio, luego respuesta normal."""
    events = await _filter(["<think>pienso</think>", "La respuesta es X."])
    assert _join_by_type(events, "thinking") == "pienso"
    assert _join_by_type(events, "token") == "La respuesta es X."


@pytest.mark.asyncio
async def test_filter_empty_think_block():
    """Bloque thinking vacío (<think></think>) no emite nada de tipo thinking."""
    events = await _filter(["antes<think></think>despues"])
    thinking = _join_by_type(events, "thinking")
    token = _join_by_type(events, "token")
    assert thinking == ""
    assert token == "antesdespues"


@pytest.mark.asyncio
async def test_filter_no_tokens():
    """Stream vacío → sin eventos."""
    events = await _filter([])
    assert events == []


@pytest.mark.asyncio
async def test_filter_only_empty_tokens():
    """Tokens vacíos no generan eventos."""
    events = await _filter(["", "", ""])
    # El buffer nunca tiene contenido, no debe emitir nada
    assert _join_by_type(events, "token") == ""
    assert _join_by_type(events, "thinking") == ""


@pytest.mark.asyncio
async def test_filter_content_before_and_after_think():
    """Texto antes y después del bloque thinking."""
    tokens = ["Intro. <think>mi razon</think> La respuesta es 42."]
    events = await _filter(tokens)
    assert _join_by_type(events, "token") == "Intro.  La respuesta es 42."
    assert _join_by_type(events, "thinking") == "mi razon"


@pytest.mark.asyncio
async def test_filter_multiple_think_blocks():
    """Varios bloques thinking intercalados."""
    tokens = ["<think>A</think>resp1<think>B</think>resp2"]
    events = await _filter(tokens)
    assert _join_by_type(events, "thinking") == "AB"
    assert _join_by_type(events, "token") == "resp1resp2"


@pytest.mark.asyncio
async def test_filter_tag_split_between_open_and_close():
    """'<think>' llega como '<' y luego 'think>' — debe detectarse correctamente."""
    events = await _filter(["texto<", "think>dentro</think>fuera"])
    assert _join_by_type(events, "token") == "textofuera"
    assert _join_by_type(events, "thinking") == "dentro"


@pytest.mark.asyncio
async def test_filter_close_tag_split():
    """'</think>' llega como '</thi' y 'nk>' — debe detectarse correctamente."""
    events = await _filter(["<think>dentro</thi", "nk>fuera"])
    assert _join_by_type(events, "thinking") == "dentro"
    assert _join_by_type(events, "token") == "fuera"


@pytest.mark.asyncio
async def test_filter_realistic_qwen3_output():
    """Simula output tipico de Qwen3 en modo thinking."""
    tokens = [
        "<think>\n",
        "El usuario pregunta sobre Python.\n",
        "Necesito dar una respuesta clara.\n",
        "</think>\n",
        "Python es un lenguaje de programacion de alto nivel.",
    ]
    events = await _filter(tokens)
    thinking = _join_by_type(events, "thinking")
    answer = _join_by_type(events, "token")
    assert "El usuario pregunta" in thinking
    assert "Python es un lenguaje" in answer
    assert "<think>" not in answer
    assert "</think>" not in answer
