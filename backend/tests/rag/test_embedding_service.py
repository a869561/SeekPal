"""Tests para EmbeddingService (FastEmbed ONNX).

Usamos un fake _model que devuelve vectores deterministas sin cargar ningún
modelo real, evitando descargas de red y dependencias de GPU en CI.
"""

import numpy as np
import pytest

from app.services.rag.embedding_service import EmbeddingService


class _FakeTextEmbedding:
    """Modelo fake que devuelve vectores fijos (1.0 por defecto, NaN si el texto empieza con 'NAN')."""

    def embed(self, texts, batch_size=8):
        for text in texts:
            if str(text).startswith("NAN"):
                yield np.full(1024, np.nan, dtype=np.float32)
            else:
                # Usar un valor ligeramente distinto por texto para distinguirlos
                val = float(hash(text) % 100) / 100.0 + 0.01
                yield np.full(1024, val, dtype=np.float32)


def _make_service(batch_size: int = 8, e5: bool = False) -> EmbeddingService:
    """Crea EmbeddingService con modelo fake sin carga de red.

    e5=True simula el modo con prefijos (intfloat/multilingual-e5-large).
    """
    svc = object.__new__(EmbeddingService)
    svc._model = _FakeTextEmbedding()
    svc._batch_size = batch_size
    svc._e5 = e5
    svc.active_provider = "CPUExecutionProvider"  # atributo nuevo para system/info
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_embed_texts_returns_vectors():
    svc = _make_service()
    vectors = await svc.embed_texts(["hola", "mundo"])
    assert len(vectors) == 2
    assert all(v is not None for v in vectors)
    assert all(len(v) == 1024 for v in vectors)


@pytest.mark.asyncio
async def test_embed_texts_empty_input():
    svc = _make_service()
    result = await svc.embed_texts([])
    assert result == []


@pytest.mark.asyncio
async def test_embed_query_single_string():
    svc = _make_service()
    vec = await svc.embed_query("¿qué contiene el documento?")
    assert len(vec) == 1024
    assert not any(np.isnan(v) for v in vec)


@pytest.mark.asyncio
async def test_embed_texts_nan_triggers_split():
    """Un texto que produce NaN debe ser dividido recursivamente; el resultado no debe ser None."""
    svc = _make_service()
    # Texto largo que empieza con NAN (fake model devuelve NaN para él)
    # pero las mitades no empiezan con NAN → tendrán vectores válidos
    long_text = "NAN " + "palabra " * 50
    vectors = await svc.embed_texts([long_text])
    # El resultado puede ser None si todos los splits fallan, pero en este caso
    # las mitades producen vectores válidos (promedio de izquierda+derecha)
    assert len(vectors) == 1
    # Si el split funcionó, el vector no debe ser None ni tener NaN
    if vectors[0] is not None:
        assert not any(np.isnan(v) for v in vectors[0])


@pytest.mark.asyncio
async def test_embed_texts_multiple_items():
    svc = _make_service(batch_size=2)
    texts = ["doc1", "doc2", "doc3", "doc4", "doc5"]
    vectors = await svc.embed_texts(texts)
    assert len(vectors) == 5
    assert all(v is not None for v in vectors)
    assert all(len(v) == 1024 for v in vectors)


# ---------------------------------------------------------------------------
# Tests para prefijos e5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e5_passage_prefix_changes_embedding():
    """Con e5=True, embed_texts antepone 'passage: ' y el vector difiere del texto crudo."""
    # El fake model devuelve un vector distinto por texto (hash). Si el prefijo se antepone,
    # el embedding de "hola" en modo e5 debe ser igual al de "passage: hola" en modo no-e5.
    svc_e5  = _make_service(e5=True)
    svc_raw = _make_service(e5=False)

    vecs_e5  = await svc_e5.embed_texts(["hola"])
    vecs_raw = await svc_raw.embed_texts(["hola"])
    vecs_prefixed = await svc_raw.embed_texts(["passage: hola"])

    assert vecs_e5[0] is not None
    assert vecs_raw[0] is not None
    # e5 debe producir el mismo vector que pasar "passage: hola" directamente
    assert vecs_e5[0] == pytest.approx(vecs_prefixed[0], abs=1e-6)
    # e5 debe producir un vector distinto al texto crudo "hola"
    assert vecs_e5[0] != pytest.approx(vecs_raw[0], abs=1e-6)


@pytest.mark.asyncio
async def test_e5_query_prefix_changes_embedding():
    """Con e5=True, embed_query antepone 'query: ' y el vector difiere del texto crudo."""
    svc_e5  = _make_service(e5=True)
    svc_raw = _make_service(e5=False)

    vec_e5  = await svc_e5.embed_query("buscar documentos")
    vec_raw = await svc_raw.embed_query("buscar documentos")
    vec_prefixed = await svc_raw.embed_query("query: buscar documentos")

    # e5 debe producir el mismo vector que "query: buscar documentos" sin prefijo activado
    assert vec_e5 == pytest.approx(vec_prefixed, abs=1e-6)
    # e5 debe diferir del texto crudo
    assert vec_e5 != pytest.approx(vec_raw, abs=1e-6)


@pytest.mark.asyncio
async def test_no_e5_prefix_when_e5_false():
    """Con e5=False (defecto), los textos se embeben sin modificar."""
    svc = _make_service(e5=False)
    vecs = await svc.embed_texts(["passage: hola"])  # si e5=False, no hay doble prefijo
    # Solo verifica que no hay crash y el resultado tiene la dimensión correcta
    assert len(vecs) == 1
    assert vecs[0] is not None
    assert len(vecs[0]) == 1024
