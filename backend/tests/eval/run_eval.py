"""Evalúa Recall@k sobre el set qa_dataset.json.

Uso:
  python -m tests.eval.run_eval --token <JWT>
  python -m tests.eval.run_eval --token <JWT> --top-k 10 --out results.csv
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


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost:3000")
    p.add_argument("--token", required=True)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--dataset", default="tests/eval/qa_dataset.json")
    p.add_argument("--out", default="tests/eval/results.csv")
    return p.parse_args()


def _stream_citations(base_url: str, token: str, question: str, top_k: int) -> list[dict]:
    with httpx.stream(
        "POST",
        f"{base_url}/api/ask",
        json={"question": question, "top_k": top_k},
        headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"},
        timeout=90.0,
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


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        return 1

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not data:
        print("Dataset is empty.", file=sys.stderr)
        return 1

    results = []
    latencies = []
    hits = 0

    for i, entry in enumerate(data, 1):
        question = entry["question"]
        expected = set(entry.get("expected_files", []))
        print(f"[{i}/{len(data)}] {question[:60]}…", end=" ", flush=True)

        t0 = time.perf_counter()
        try:
            citations = _stream_citations(args.base_url, args.token, question, args.top_k)
        except Exception as exc:
            print(f"ERROR: {exc}")
            citations = []
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        retrieved_files = {c["file_name"] for c in citations}
        hit = bool(expected & retrieved_files) if expected else None
        if hit:
            hits += 1

        results.append({
            "question": question,
            "retrieved": "; ".join(sorted(retrieved_files)),
            "expected": "; ".join(sorted(expected)),
            "hit": hit,
            "latency_ms": round(elapsed_ms, 1),
            "notes": entry.get("notes", ""),
        })
        status = "✓" if hit else ("?" if hit is None else "✗")
        print(f"{status}  {elapsed_ms:.0f} ms")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["question", "retrieved", "expected", "hit", "latency_ms", "notes"])
        w.writeheader()
        w.writerows(results)

    labeled = [r for r in results if r["hit"] is not None]
    if labeled:
        recall = sum(1 for r in labeled if r["hit"]) / len(labeled)
        print(f"\nRecall@{args.top_k}: {recall:.3f}  ({sum(1 for r in labeled if r['hit'])}/{len(labeled)} labeled)")
    else:
        print("\nNo labeled entries — fill in expected_files in qa_dataset.json to measure Recall@k.")

    print(f"Latency P50: {statistics.median(latencies):.0f} ms")
    if len(latencies) >= 4:
        p95_idx = max(0, int(len(latencies) * 0.95) - 1)
        p95 = sorted(latencies)[p95_idx]
        print(f"Latency P95: {p95:.0f} ms")

    print(f"Results saved to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
