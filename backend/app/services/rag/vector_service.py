"""Wrapper sobre QdrantClient con soporte de búsqueda híbrida dense+sparse.

La colección usa dos campos vectoriales:
  - "dense"  (1024D cosine) → embeddings BGE-M3
  - "bm25"   (sparse IDF)   → tokens BM25 via FastEmbed Qdrant/bm25

La búsqueda fusiona ambas ramas con Reciprocal Rank Fusion (RRF).

LIMITACIÓN: QdrantClient(path=...) no es thread-safe ni multi-proceso-safe.
Usar siempre uvicorn --workers 1 con este modo. Para escalado horizontal,
migrar a QdrantClient(host=...) con servidor independiente.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.services.rag.types import RetrievedChunk

_DENSE_PREFETCH_MULT  = 4  # Prefetch top_k × 4 para la rama densa (alta cobertura semántica)
_SPARSE_PREFETCH_MULT = 2  # Prefetch top_k × 2 para BM25 (menos candidatos → menos ruido en docs cortos)


class VectorService:
    def __init__(self, path: str, collection: str, dim: int = 1024):
        self._client = QdrantClient(path=path)
        self._collection = collection
        self._dim = dim

    def ensure_collection(self) -> None:
        """Crea o migra la colección al esquema hybrid dense+sparse.

        Si ya existe una colección con el esquema antiguo (vector anónimo sin sparse),
        la elimina y la recrea. Esto requiere re-ingestar las fuentes.
        """
        existing = {c.name for c in self._client.get_collections().collections}
        if self._collection in existing:
            info = self._client.get_collection(self._collection)
            params = info.config.params
            # qdrant-client ≥1.16: atributos son 'sparse_vectors' y 'vectors'
            has_sparse = bool(
                getattr(params, "sparse_vectors", None)
                or getattr(params, "sparse_vectors_config", None)
            )
            vectors_field = getattr(params, "vectors", None) or getattr(params, "vectors_config", None)
            has_named = isinstance(vectors_field, dict)
            if has_sparse and has_named:
                return  # Esquema hybrid ya presente
            # Esquema antiguo (dense anónimo, sin sparse) → migrar
            print(
                f"[seekpal] Colección '{self._collection}' sin vectores sparse. "
                "Eliminando para migrar al esquema hybrid dense+BM25. "
                "Re-ingesta de fuentes necesaria."
            )
            self._client.delete_collection(self._collection)

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={"dense": qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE)},
            sparse_vectors_config={"bm25": qm.SparseVectorParams(modifier=qm.Modifier.IDF)},
        )
        for field, schema in [
            ("file_id",   qm.PayloadSchemaType.KEYWORD),
            ("source_id", qm.PayloadSchemaType.KEYWORD),
            ("category",  qm.PayloadSchemaType.KEYWORD),
        ]:
            self._client.create_payload_index(self._collection, field, schema)

    def upsert(
        self,
        points: list[tuple[str, list[float], qm.SparseVector, dict]],
    ) -> None:
        """Inserta/actualiza puntos con vector denso y sparse BM25.

        Args:
            points: lista de (chunk_id, dense_vector, sparse_vector, payload)
        """
        if not points:
            return
        qd_points = [
            qm.PointStruct(
                id=_str_to_uuid(pid),
                vector={
                    "dense": dense_vec,
                    "bm25": sparse_vec,
                },
                payload=payload,
            )
            for pid, dense_vec, sparse_vec, payload in points
        ]
        self._client.upsert(collection_name=self._collection, points=qd_points)

    def search(
        self,
        dense_vector: list[float],
        sparse_vector: qm.SparseVector,
        top_k: int,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Búsqueda híbrida dense+sparse con fusión RRF."""
        qf = _build_filter(filters) if filters else None
        dense_limit  = max(top_k * _DENSE_PREFETCH_MULT,  20)
        sparse_limit = max(top_k * _SPARSE_PREFETCH_MULT, 20)

        response = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                qm.Prefetch(query=dense_vector, using="dense", limit=dense_limit,  filter=qf),
                qm.Prefetch(query=sparse_vector, using="bm25",  limit=sparse_limit, filter=qf),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=top_k,
            with_payload=True,
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
