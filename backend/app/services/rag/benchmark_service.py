"""Framework de evaluacion del pipeline RAG.

Metricas implementadas:
  - Recall@k   : fraccion de documentos relevantes recuperados en top-k
  - MRR        : Mean Reciprocal Rank â€” posicion media del primer resultado correcto
  - Latency p50/p95/p99 : percentiles de latencia de retrieval en ms

Uso basico:
  >>> from app.services.rag.benchmark_service import BenchDataset, score_pipeline
  >>> dataset = BenchDataset.from_list([
  ...     {"question": "?Que es X?", "relevant_ids": ["file::0", "file::1"]},
  ... ])
  >>> report = await score_pipeline(dataset, retribenchmark_service, top_k=10)
  >>> print(report.summary())
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# Tipos de datos
# --------------------------------------------------------------------------

@dataclass
class BenchQuery:
    """Una pregunta de evaluacion con sus chunk_ids relevantes esperados."""
    question: str
    relevant_ids: list[str]           # chunk_ids que son ground-truth
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Resultado de evaluar una sola query."""
    question: str
    retrieved_ids: list[str]          # chunk_ids recuperados (ordenados por rank)
    relevant_ids: list[str]           # ground-truth
    recall_at_k: float                # TP / |relevant|
    reciprocal_rank: float            # 1/rank del primer hit (0 si sin hit)
    latency_ms: float                 # tiempo de retrieval en ms


@dataclass
class BenchReport:
    """Resultados agregados de un conjunto de queries de evaluacion."""
    num_queries: int
    top_k: int
    mean_recall: float                # promedio de recall@k
    mrr: float                        # Mean Reciprocal Rank
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    per_query: list[QueryResult] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Evaluation Report ({self.num_queries} queries, top_k={self.top_k})",
            f"  Recall@{self.top_k}  : {self.mean_recall:.3f}",
            f"  MRR          : {self.mrr:.3f}",
            f"  Latency p50  : {self.latency_p50_ms:.1f} ms",
            f"  Latency p95  : {self.latency_p95_ms:.1f} ms",
            f"  Latency p99  : {self.latency_p99_ms:.1f} ms",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchDataset:
    """Conjunto de queries de evaluacion."""
    queries: list[BenchQuery]

    @classmethod
    def from_list(cls, data: list[dict]) -> "BenchDataset":
        """Crea un BenchDataset desde una lista de dicts con 'question' y 'relevant_ids'."""
        queries = [
            BenchQuery(
                question=item["question"],
                relevant_ids=list(item["relevant_ids"]),
                metadata=item.get("metadata", {}),
            )
            for item in data
        ]
        return cls(queries=queries)

    @classmethod
    def from_json(cls, path: Path | str) -> "BenchDataset":
        """Carga desde un fichero JSON con array de {question, relevant_ids}."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_list(data)

    def to_json(self, path: Path | str) -> None:
        """Serializa el dataset a JSON."""
        data = [
            {"question": q.question, "relevant_ids": q.relevant_ids, "metadata": q.metadata}
            for q in self.queries
        ]
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def __len__(self) -> int:
        return len(self.queries)


# --------------------------------------------------------------------------
# Metricas individuales (puras â€” sin dependencias externas, facil de testear)
# --------------------------------------------------------------------------

def recall_at_k(retrieved: list[str], relevant: set[str]) -> float:
    """Fraccion de documentos relevantes que aparecen en retrieved.

    recall@k = |retrieved âˆ© relevant| / |relevant|

    Si relevant esta vacio devuelve 1.0 â€” no hay nada que recuperar.
    """
    if not relevant:
        return 1.0
    hits = sum(1 for r in retrieved if r in relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """1 / rank del primer resultado relevante en retrieved (base 1).

    Devuelve 0.0 si ningun resultado es relevante.
    """
    for rank, r in enumerate(retrieved, start=1):
        if r in relevant:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(rr_values: list[float]) -> float:
    """MRR de una lista de reciprocal ranks."""
    if not rr_values:
        return 0.0
    return sum(rr_values) / len(rr_values)


def percentile(values: list[float], p: float) -> float:
    """Percentil p (0-100) de una lista de valores.

    Usa interpolacion lineal entre los dos valores adyacentes.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = (p / 100.0) * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


# --------------------------------------------------------------------------
# Runner principal
# --------------------------------------------------------------------------

async def score_pipeline(
    dataset: BenchDataset,
    retribenchmark_service: Any,
    top_k: int = 10,
    source_id: str | None = None,
    categories: list[str] | None = None,
    concurrency: int = 4,
) -> BenchReport:
    """Ejecuta el pipeline de retrieval sobre el dataset y calcula metricas.

    Args:
        dataset: conjunto de (question, relevant_ids)
        retribenchmark_service: instancia de RetrievalService (o compatible)
        top_k: numero de chunks a recuperar por query
        source_id: filtrar por fuente (None = todas)
        categories: filtrar por categoria (None = todas)
        concurrency: queries paralelas maximas (limitar para no saturar Qdrant)

    Returns:
        BenchReport con metricas agregadas y resultados por query
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _score_one(query: BenchQuery) -> QueryResult:
        async with semaphore:
            t0 = time.perf_counter()
            chunks = await retribenchmark_service.retrieve(
                question=query.question,
                top_k=top_k,
                source_id=source_id,
                categories=categories,
            )
            latency_ms = (time.perf_counter() - t0) * 1000.0

            retrieved_ids = [c.chunk_id for c in chunks]
            relevant_set = set(query.relevant_ids)

            return QueryResult(
                question=query.question,
                retrieved_ids=retrieved_ids,
                relevant_ids=query.relevant_ids,
                recall_at_k=recall_at_k(retrieved_ids, relevant_set),
                reciprocal_rank=reciprocal_rank(retrieved_ids, relevant_set),
                latency_ms=latency_ms,
            )

    results: list[QueryResult] = list(
        await asyncio.gather(*[_score_one(q) for q in dataset.queries])
    )

    latencies = [r.latency_ms for r in results]
    recalls = [r.recall_at_k for r in results]
    rrs = [r.reciprocal_rank for r in results]

    return BenchReport(
        num_queries=len(results),
        top_k=top_k,
        mean_recall=sum(recalls) / len(recalls) if recalls else 0.0,
        mrr=mean_reciprocal_rank(rrs),
        latency_p50_ms=percentile(latencies, 50),
        latency_p95_ms=percentile(latencies, 95),
        latency_p99_ms=percentile(latencies, 99),
        per_query=results,
    )
