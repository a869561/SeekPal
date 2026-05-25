"""Evalúa Recall@k sobre el set qa_dataset.json.

Uso rápido (hace login + ingesta + eval automáticamente):
  python -m tests.eval.run_eval --password TU_CONTRASEÑA

Opciones avanzadas:
  python -m tests.eval.run_eval --password TU_CONTRASEÑA --top-k 8 --out results.csv
  python -m tests.eval.run_eval --token JWT_TOKEN --skip-ingest  # si ya está ingestado
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

import httpx


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:3000")
    p.add_argument("--password", default=None,
                   help="Contraseña de SeekPal (hace login automático)")
    p.add_argument("--token", default=None,
                   help="JWT ya obtenido (alternativa a --password)")
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--dataset",
                   default=str(Path(__file__).parent / "qa_dataset.json"))
    p.add_argument("--corpus",
                   default=str(Path(__file__).parent / "corpus"),
                   help="Directorio a ingestar como fuente de prueba")
    p.add_argument("--skip-ingest", action="store_true",
                   help="Saltar ingesta (corpus ya ingestado)")
    p.add_argument("--out",
                   default=str(Path(__file__).parent / "results.csv"))
    return p.parse_args()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login(base_url: str, password: str) -> str:
    r = httpx.post(f"{base_url}/api/auth/login",
                   json={"password": password}, timeout=10)
    r.raise_for_status()
    token = r.json().get("accessToken") or r.json().get("token")
    if not token:
        raise RuntimeError(f"Login OK pero sin token: {r.json()}")
    return token


# ---------------------------------------------------------------------------
# Ingesta
# ---------------------------------------------------------------------------

def add_source(base_url: str, token: str, path: str, name: str) -> str:
    """Crea una fuente y devuelve su ID."""
    r = httpx.post(f"{base_url}/api/sources",
                   json={"name": name, "path": path},
                   headers={"Authorization": f"Bearer {token}"},
                   timeout=10)
    r.raise_for_status()
    return r.json()["data"]["_id"]


def wait_for_ingest(base_url: str, token: str, source_id: str,
                    timeout: int = 300) -> None:
    """Lanza la ingesta y espera a que termine (máx timeout segundos)."""
    # Lanzar ingesta (SSE — no esperamos el stream, lo cerramos enseguida)
    with httpx.stream(
        "POST",
        f"{base_url}/api/sources/{source_id}/ingest",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "text/event-stream"},
        timeout=timeout,
    ) as r:
        r.raise_for_status()
        t0 = time.monotonic()
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            etype = evt.get("type", "")
            if etype == "scan_done":
                n = evt.get("data", {}).get("total", "?")
                print(f"    Escaneados {n} ficheros, indexando…", flush=True)
            elif etype == "done":
                print("    Ingesta completada.", flush=True)
                return
            elif etype == "error":
                raise RuntimeError(f"Error en ingesta: {evt}")
            elif time.monotonic() - t0 > timeout:
                raise TimeoutError("Ingesta demasiado lenta")


# ---------------------------------------------------------------------------
# Eval
# ---------------------------------------------------------------------------

def stream_citations(base_url: str, token: str,
                     question: str, top_k: int) -> list[dict]:
    with httpx.stream(
        "POST",
        f"{base_url}/api/ask",
        json={"question": question, "top_k": top_k},
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "text/event-stream"},
        timeout=120.0,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "retrieved":
                return evt.get("citations", [])
            if evt.get("type") in ("done", "error"):
                break
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    # --- Token ---
    if args.token:
        token = args.token
    elif args.password:
        print("  Iniciando sesión…", flush=True)
        try:
            token = login(args.base_url, args.password)
            print("  Login OK.", flush=True)
        except Exception as exc:
            print(f"ERROR al hacer login: {exc}", file=sys.stderr)
            return 1
    else:
        print("ERROR: proporciona --password o --token", file=sys.stderr)
        return 1

    # --- Ingesta ---
    corpus_path = Path(args.corpus).resolve()
    if not args.skip_ingest:
        if not corpus_path.exists():
            print(f"ERROR: corpus no encontrado: {corpus_path}", file=sys.stderr)
            return 1
        print(f"  Añadiendo corpus '{corpus_path.name}' como fuente…", flush=True)
        try:
            source_id = add_source(args.base_url, token,
                                   str(corpus_path), "eval-corpus")
            print(f"  Fuente creada ({source_id}). Ingestando…", flush=True)
            wait_for_ingest(args.base_url, token, source_id)
        except Exception as exc:
            print(f"ERROR en ingesta: {exc}", file=sys.stderr)
            print("  Prueba con --skip-ingest si el corpus ya está ingestado.")
            return 1

    # --- Cargar dataset ---
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset no encontrado: {dataset_path}", file=sys.stderr)
        return 1
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not data:
        print("Dataset vacío.", file=sys.stderr)
        return 1

    # --- Evaluación ---
    print(f"\n{'='*60}")
    print(f"  EVALUACION -- {len(data)} preguntas, top_k={args.top_k}")
    print(f"{'='*60}\n")

    results = []
    latencies = []
    hits = 0
    labeled_count = 0

    for i, entry in enumerate(data, 1):
        question = entry["question"]
        expected = set(entry.get("expected_files", []))
        hint = entry.get("expected_answer_hint", "")
        print(f"[{i:02d}/{len(data)}] {question[:65]}…", end=" ", flush=True)

        t0 = time.perf_counter()
        try:
            citations = stream_citations(args.base_url, token, question, args.top_k)
        except Exception as exc:
            print(f"ERROR: {exc}")
            citations = []
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        retrieved_files = {c["file_name"] for c in citations}
        if expected:
            hit = bool(expected & retrieved_files)
            labeled_count += 1
            if hit:
                hits += 1
        else:
            hit = None

        status = "OK" if hit else ("??" if hit is None else "FAIL")
        print(f"{status:<5}  {elapsed_ms:.0f} ms")
        if hit is False:
            print(f"       Esperado: {expected}")
            print(f"       Obtenido: {retrieved_files}")

        results.append({
            "question": question,
            "retrieved": "; ".join(sorted(retrieved_files)),
            "expected": "; ".join(sorted(expected)),
            "hit": hit,
            "latency_ms": round(elapsed_ms, 1),
            "answer_hint": hint,
            "notes": entry.get("notes", ""),
        })

    # --- Resumen ---
    sep = "=" * 60
    print(f"\n{sep}")
    if labeled_count:
        recall = hits / labeled_count
        print(f"  Recall@{args.top_k}: {recall:.1%}  ({hits}/{labeled_count} recuperados)")
    if latencies:
        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]
        print(f"  Latencia P50: {p50:.0f} ms   P95: {p95:.0f} ms")
    print(f"{sep}\n")

    # --- CSV ---
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "question", "retrieved", "expected", "hit",
            "latency_ms", "answer_hint", "notes"
        ])
        w.writeheader()
        w.writerows(results)
    print(f"  Resultados guardados en: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
