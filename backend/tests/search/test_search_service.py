"""Tests unitarios del servicio de búsqueda (search_service.py).

Cubre los tres modos:
  1. _semantic_search  — Qdrant disponible → devuelve docs relevantes ordenados por score
  2. _semantic_search  — Qdrant lanza excepción → cae a _filename_search (fallback)
  3. _filename_search  — búsqueda por regex de nombre de fichero
  4. _list_files       — sin query → listado paginado de todos los ficheros
  5. search()          — router principal: sin query → _list_files, con query → semántica

Todas las dependencias externas (Qdrant, MongoDB) se simulan con mocks.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub de beanie.PydanticObjectId — evita importar MongoDB real
# ---------------------------------------------------------------------------

import re as _re

_OID_RE = _re.compile(r"^[0-9a-fA-F]{24}$")


class _FakeOid(str):
    """Simula PydanticObjectId: solo acepta strings de 24 caracteres hexadecimales."""
    def __new__(cls, value):
        s = str(value)
        if not _OID_RE.match(s):
            raise ValueError(f"Invalid ObjectId: {s!r}")
        return str.__new__(cls, s)


# Parchear beanie antes de importar search_service
_beanie_stub = types.ModuleType("beanie")
_beanie_stub.PydanticObjectId = _FakeOid
sys.modules.setdefault("beanie", _beanie_stub)

# Stub para app.models.file
_file_model_stub = types.ModuleType("app.models.file")


class _FakeFileDoc:
    _pymongo_col = None

    @classmethod
    def get_pymongo_collection(cls):
        return cls._pymongo_col


_file_model_stub.FileDoc = _FakeFileDoc
sys.modules["app.models.file"] = _file_model_stub

# Stub para app.core.database (retrieval service se inyecta por tests)
_db_stub = types.ModuleType("app.core.database")
_db_stub._retrieval_svc = None


def _get_retrieval_service():
    return _db_stub._retrieval_svc


_db_stub.get_retrieval_service = _get_retrieval_service
sys.modules["app.core.database"] = _db_stub

# Finalmente importar el módulo bajo prueba
from app.services import search_service  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(file_id: str, score: float, text: str = "fragmento de texto"):
    """Crea un RetrievedChunk mínimo para los tests."""
    from app.services.rag.types import RetrievedChunk

    return RetrievedChunk(
        chunk_id=f"chunk-{file_id}",
        file_id=file_id,
        source_id="src-001",
        text=text,
        page=1,
        offset_start=0,
        offset_end=len(text),
        file_name=f"doc_{file_id}.pdf",
        category="document",
        extension=".pdf",
        score=score,
    )


def _fake_file_doc(file_id: str, name: str = "doc.pdf"):
    """Devuelve un dict MongoDB-like para un fichero."""
    return {"_id": file_id, "name": name, "category": "document",
            "size": 1024, "path": f"/data/{name}", "metadata": {}}


def _make_mongo_col(docs: list[dict]):
    """Construye un cursor MongoDB falso que devuelve docs."""
    col = MagicMock()
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    cursor.sort.return_value = cursor
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    col.find.return_value = cursor
    col.count_documents = AsyncMock(return_value=len(docs))
    return col


# ══════════════════════════════════════════════════════════════════════════
# 1. Búsqueda semántica — resultado ordenado por relevancia
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_semantic_search_returns_files_sorted_by_score():
    """Chunks de Qdrant → ficheros únicos ordenados de mayor a menor score."""
    fid_a = "a" * 24
    fid_b = "b" * 24

    chunks = [
        _make_chunk(fid_a, score=0.91, text="El cambio climático afecta..."),
        _make_chunk(fid_b, score=0.75, text="Energías renovables..."),
        _make_chunk(fid_a, score=0.60, text="Segunda mención climática"),  # mismo fid que a
    ]

    # Retrieval devuelve los 3 chunks; fid_a debe ganar con score 0.91
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(return_value=chunks)
    _db_stub._retrieval_svc = mock_retrieval

    docs = [_fake_file_doc(fid_a, "clima.pdf"), _fake_file_doc(fid_b, "energia.pdf")]
    _FakeFileDoc._pymongo_col = _make_mongo_col(docs)

    result = await search_service.search(
        q="cambio climático",
        category=None,
        source_id=None,
        page=1,
        limit=10,
    )

    assert result["total"] == 2             # 2 ficheros únicos
    assert result["page"] == 1
    files = result["files"]
    assert len(files) == 2
    # El primero debe ser fid_a (score 0.91 > 0.75)
    assert str(files[0]["_id"]) == fid_a
    assert files[0]["_relevanceScore"] == pytest.approx(0.91, abs=0.001)
    assert "_snippet" in files[0]


@pytest.mark.asyncio
async def test_semantic_search_snippet_comes_from_best_chunk():
    """El snippet adjunto al fichero debe ser el del chunk con mayor score."""
    fid = "c" * 24
    chunks = [
        _make_chunk(fid, score=0.50, text="Texto menos relevante"),
        _make_chunk(fid, score=0.88, text="Este es el fragmento más relevante"),
    ]
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(return_value=chunks)
    _db_stub._retrieval_svc = mock_retrieval

    _FakeFileDoc._pymongo_col = _make_mongo_col([_fake_file_doc(fid)])

    result = await search_service.search(q="relevante", category=None, source_id=None,
                                         page=1, limit=10)
    assert result["files"][0]["_snippet"] == "Este es el fragmento más relevante"


@pytest.mark.asyncio
async def test_semantic_search_pagination():
    """Con limit=1 y 2 ficheros únicos, la página 2 devuelve el segundo."""
    fid_a, fid_b = "d" * 24, "e" * 24
    chunks = [
        _make_chunk(fid_a, score=0.9),
        _make_chunk(fid_b, score=0.8),
    ]
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(return_value=chunks)
    _db_stub._retrieval_svc = mock_retrieval

    _FakeFileDoc._pymongo_col = _make_mongo_col([_fake_file_doc(fid_b)])

    result = await search_service.search(q="texto", category=None, source_id=None,
                                         page=2, limit=1)
    assert result["total"] == 2
    assert result["pages"] == 2
    assert len(result["files"]) == 1


@pytest.mark.asyncio
async def test_semantic_search_empty_chunks_returns_empty():
    """Sin chunks devuelve lista vacía y total 0."""
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(return_value=[])
    _db_stub._retrieval_svc = mock_retrieval

    result = await search_service.search(q="inexistente", category=None, source_id=None,
                                         page=1, limit=10)
    assert result["files"] == []
    assert result["total"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 2. Fallback por nombre cuando Qdrant falla
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fallback_when_retrieval_raises():
    """Si retrieve() lanza excepción, se usa _filename_search (regex MongoDB)."""
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(side_effect=RuntimeError("Qdrant unavailable"))
    _db_stub._retrieval_svc = mock_retrieval

    fid = "f" * 24
    _FakeFileDoc._pymongo_col = _make_mongo_col([_fake_file_doc(fid, "python_tutorial.pdf")])

    result = await search_service.search(q="python tutorial", category=None,
                                         source_id=None, page=1, limit=10)
    # Debe devolver resultados aunque Qdrant falló
    assert result is not None
    assert "files" in result
    assert "total" in result


@pytest.mark.asyncio
async def test_fallback_when_retrieval_none():
    """Si get_retrieval_service() devuelve None, usa _filename_search."""
    _db_stub._retrieval_svc = None

    fid = "0" * 24
    col = _make_mongo_col([_fake_file_doc(fid, "economia.pdf")])
    _FakeFileDoc._pymongo_col = col

    result = await search_service.search(q="economia", category=None,
                                         source_id=None, page=1, limit=10)
    assert "files" in result
    assert "total" in result


# ══════════════════════════════════════════════════════════════════════════
# 3. Sin query → _list_files
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_no_query_calls_list_files():
    """Sin query la función devuelve todos los ficheros ordenados."""
    fid1, fid2 = "1" * 24, "2" * 24
    docs = [_fake_file_doc(fid1, "alfa.pdf"), _fake_file_doc(fid2, "zeta.pdf")]
    _FakeFileDoc._pymongo_col = _make_mongo_col(docs)

    # El retrieval NO debe ser llamado
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock()
    _db_stub._retrieval_svc = mock_retrieval

    result = await search_service.search(q=None, category=None,
                                         source_id=None, page=1, limit=10)
    assert result["total"] == 2
    mock_retrieval.retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_string_query_uses_list_files():
    """Query vacío ('') o solo espacios también activa _list_files."""
    _FakeFileDoc._pymongo_col = _make_mongo_col([])
    result = await search_service.search(q="   ", category=None,
                                         source_id=None, page=1, limit=10)
    # No debe fallar y debe devolver estructura correcta
    assert "files" in result
    assert "total" in result


# ══════════════════════════════════════════════════════════════════════════
# 4. Helpers internos
# ══════════════════════════════════════════════════════════════════════════

def test_is_valid_oid_accepts_24_hex():
    assert search_service._is_valid_oid("a" * 24) is True


def test_is_valid_oid_rejects_invalid():
    assert search_service._is_valid_oid("bad_id") is False
    assert search_service._is_valid_oid("") is False


# ══════════════════════════════════════════════════════════════════════════
# 5. Paginación — estructura de la respuesta
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_response_always_has_required_keys():
    """La respuesta siempre incluye files, total, page, pages."""
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(return_value=[])
    _db_stub._retrieval_svc = mock_retrieval

    result = await search_service.search(q="test", category=None,
                                         source_id=None, page=1, limit=10)
    for key in ("files", "total", "page", "pages"):
        assert key in result, f"Falta la clave '{key}' en la respuesta"


@pytest.mark.asyncio
async def test_pages_calculated_correctly():
    """pages = ceil(total / limit)."""
    fids = [str(i) * 24 for i in range(1, 6)]  # 5 ficheros
    chunks = [_make_chunk(fid, score=float(i) / 10) for i, fid in enumerate(fids, 1)]

    mock_retrieval = MagicMock()
    mock_retrieval.retrieve = AsyncMock(return_value=chunks)
    _db_stub._retrieval_svc = mock_retrieval

    _FakeFileDoc._pymongo_col = _make_mongo_col([_fake_file_doc(fids[0])])

    result = await search_service.search(q="datos", category=None,
                                         source_id=None, page=1, limit=2)
    assert result["total"] == 5
    assert result["pages"] == 3  # ceil(5/2) = 3
