"""Re-triggers ingestion for an existing source and streams progress."""
import httpx
import json
import sys

TOKEN = sys.argv[1]
SOURCE_ID = sys.argv[2]
BASE = "http://localhost:3000"

print(f"Re-ingesting source {SOURCE_ID}...", flush=True)
with httpx.stream(
    "POST", f"{BASE}/api/sources/{SOURCE_ID}/ingest",
    headers={"Authorization": f"Bearer {TOKEN}", "Accept": "text/event-stream"},
    timeout=300.0,
) as r:
    print(f"Status: {r.status_code}", flush=True)
    r.raise_for_status()
    for line in r.iter_lines():
        if not line.startswith("data:"):
            continue
        try:
            evt = json.loads(line[5:].strip())
        except Exception:
            continue
        t = evt.get("type", "")
        d = evt.get("data", {})
        if t == "scan_done":
            print(f"  Scanned: {d.get('total', '?')} files", flush=True)
        elif t == "progress":
            msg = d.get("message", "")
            if msg:
                print(f"  {msg}", flush=True)
        elif t == "done":
            print("  Ingestion complete!", flush=True)
            sys.exit(0)
        elif t == "error":
            print(f"  ERROR: {evt}", file=sys.stderr, flush=True)
            sys.exit(1)
        elif t == "heartbeat":
            print(".", end="", flush=True)
