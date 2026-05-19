"""Wrapper sobre QdrantClient (modo embebido file-based o :memory: para tests).

LIMITACIÓN: QdrantClient(path=...) no es thread-safe ni multi-proceso-safe.
Usar siempre uvicorn --workers 1 con este modo. Para escalado horizontal,
migrar a QdrantClient(host=...) con servidor independiente.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.services.rag.types import RetrievedChunk


class VectorService:
    def __init__(self, path: str, collection: str, dim: int = 1024):
        self._client = QdrantClient(path=path)
        self._collection = collection
        self._dim = dim

    def ensure_collection(self) -> None:
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection in existing:
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE),
        )
        self._client.create_payload_index(
            self._collection, "file_id", qm.PayloadSchemaType.KEYWORD
        )
        self._client.create_payload_index(
            self._collection, "source_id", qm.PayloadSchemaType.KEYWORD
        )

    def upsert(self, points: list[tuple[str, list[float], dict]]) -> None:
        if not points:
            return
        qd_points = [
            qm.PointStruct(id=_str_to_uuid(pid), vector=vec, payload=payload)
            for pid, vec, payload in points
        ]
        self._client.upsert(collection_name=self._collection, points=qd_points)

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        qf = _build_filter(filters) if filters else None
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
            query_filter=qf,
        )
        return [_to_retrieved(r) for r in response.points]

    def delete_by_file(self, file_id: str) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(filter=qm.Filter(
                must=[qm.FieldCondition(key="file_id", match=qm.MatchValue(value=file_id))]
            )),
        )

    def delete_by_source(self, source_id: str) -> None:
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(filter=qm.Filter(
                must=[qm.FieldCondition(key="source_id", match=qm.MatchValue(value=source_id))]
            )),
        )

    def count(self) -> int:
        return self._client.count(collection_name=self._collection, exact=True).count

    def close(self) -> None:
        self._client.close()


def _build_filter(filters: dict) -> qm.Filter:
    must = []
    for key, value in filters.items():
        if isinstance(value, list):
            must.append(qm.FieldCondition(key=key, match=qm.MatchAny(any=value)))
        else:
            must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))
    return qm.Filter(must=must)


def _to_retrieved(point) -> RetrievedChunk:
    p = point.payload or {}
    return RetrievedChunk(
        chunk_id=p.get("chunk_id", ""),
        file_id=p.get("file_id", ""),
        source_id=p.get("source_id", ""),
        text=p.get("text", ""),
        page=p.get("page"),
        offset_start=p.get("offset_start", 0),
        offset_end=p.get("offset_end", 0),
        file_name=p.get("file_name", ""),
        category=p.get("category", "other"),
        extension=p.get("extension", ""),
        score=float(point.score),
    )


def _str_to_uuid(s: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, s))
