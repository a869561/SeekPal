"""Servicio de búsqueda de documentos.

Modo con query:
  Búsqueda semántica híbrida (dense+BM25) via Qdrant.
  Los chunks se agrupan por fichero y se ordenan por relevancia descendente.
  Si Qdrant no está disponible cae a búsqueda por nombre (regex MongoDB).

Modo sin query:
  Lista todos los ficheros con filtros opcionales de categoría y fuente.
"""
from __future__ import annotations

import re

from beanie import PydanticObjectId

from app.models.file import FileDoc

_SPECIAL_REGEX = re.compile(r"[.*+?^${}()|\[\]\\]")

# Cuántos chunks pedir a Qdrant antes de agrupar por fichero.
# 80 chunks cubre sobradamente las 2-3 páginas típicas de resultados (15/pág)
# sin sobrecargar el prefetch de RRF (que multiplica × 4 internamente).
_CHUNK_LIMIT = 80


async def search(
    q: str | None,
    category: str | None,
    source_id: str | None,
    page: int,
    limit: int,
) -> dict:
    if q and q.strip():
        return await _semantic_search(q.strip(), category, source_id, page, limit)
    return await _list_files(category, source_id, page, limit)


# ── Búsqueda semántica ────────────────────────────────────────────────────

async def _semantic_search(
    q: str,
    category: str | None,
    source_id: str | None,
    page: int,
    limit: int,
) -> dict:
    """Busca documentos relevantes por contenido usando búsqueda híbrida Qdrant."""
    from app.core.database import get_retrieval_service  # import tardío para evitar ciclos

    retrieval = get_retrieval_service()
    if retrieval is None:
        # Backend aún arrancando o Qdrant no disponible → fallback
        return await _filename_search(q, category, source_id, page, limit)

    try:
        chunks = await retrieval.retrieve(
            question=q,
            top_k=_CHUNK_LIMIT,
            source_id=source_id or None,
            categories=[category] if category else None,
        )
    except Exception:
        return await _filename_search(q, category, source_id, page, limit)

    if not chunks:
        return {"files": [], "total": 0, "page": page, "pages": 1}

    # Agrupar por file_id: conservar el mejor score y el fragmento más relevante
    best: dict[str, dict] = {}
    for chunk in chunks:
        fid = chunk.file_id
        if fid not in best or chunk.score > best[fid]["score"]:
            best[fid] = {
                "score": chunk.score,
                "snippet": chunk.text.strip()[:300],
            }

    # Ordenar por relevancia y paginar
    sorted_ids = sorted(best, key=lambda fid: best[fid]["score"], reverse=True)
    total = len(sorted_ids)
    page_ids = sorted_ids[(page - 1) * limit: page * limit]

    if not page_ids:
        return {
            "files": [],
            "total": total,
            "page": page,
            "pages": max((total + limit - 1) // limit, 1),
        }

    # Obtener metadatos de MongoDB para los ficheros de esta página
    obj_ids = [PydanticObjectId(fid) for fid in page_ids if _is_valid_oid(fid)]
    files_col = FileDoc.get_pymongo_collection()
    cursor = files_col.find({"_id": {"$in": obj_ids}})
    files_raw = await cursor.to_list(length=limit)

    # Reordenar según relevancia y añadir score + snippet
    file_map = {str(f["_id"]): f for f in files_raw}
    result_files = []
    for fid in page_ids:
        f = file_map.get(fid)
        if f:
            f["_relevanceScore"] = round(best[fid]["score"], 4)
            f["_snippet"] = best[fid]["snippet"]
            result_files.append(f)

    return {
        "files": result_files,
        "total": total,
        "page": page,
        "pages": max((total + limit - 1) // limit, 1),
    }


# ── Listar ficheros (sin query) ───────────────────────────────────────────

async def _list_files(
    category: str | None,
    source_id: str | None,
    page: int,
    limit: int,
) -> dict:
    """Lista ficheros ordenados por nombre cuando no hay query."""
    fq: dict = {}
    if category:
        fq["category"] = category
    if source_id and _is_valid_oid(source_id):
        fq["sourceId"] = PydanticObjectId(source_id)

    skip = (page - 1) * limit
    col = FileDoc.get_pymongo_collection()
    files = await col.find(fq).sort("name", 1).skip(skip).limit(limit).to_list(length=limit)
    total = await col.count_documents(fq)

    return {
        "files": files,
        "total": total,
        "page": page,
        "pages": max((total + limit - 1) // limit, 1),
    }


# ── Fallback por nombre ───────────────────────────────────────────────────

async def _filename_search(
    q: str,
    category: str | None,
    source_id: str | None,
    page: int,
    limit: int,
) -> dict:
    """Fallback: regex sobre nombre y ruta del fichero (MongoDB)."""
    words = [_SPECIAL_REGEX.sub(lambda m: f"\\{m.group(0)}", w) for w in q.split()]
    pattern = "|".join(w for w in words if w)
    fq: dict = {}
    if pattern:
        rx = {"$regex": pattern, "$options": "i"}
        fq["$or"] = [{"name": rx}, {"path": rx}]
    if category:
        fq["category"] = category
    if source_id and _is_valid_oid(source_id):
        fq["sourceId"] = PydanticObjectId(source_id)

    skip = (page - 1) * limit
    col = FileDoc.get_pymongo_collection()
    files = await col.find(fq).sort("name", 1).skip(skip).limit(limit).to_list(length=limit)
    total = await col.count_documents(fq)

    return {
        "files": files,
        "total": total,
        "page": page,
        "pages": max((total + limit - 1) // limit, 1),
    }


def _is_valid_oid(s: str) -> bool:
    try:
        PydanticObjectId(s)
        return True
    except Exception:
        return False
