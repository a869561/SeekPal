"""Ingesta el corpus de evaluación y muestra progreso."""
import httpx, json, sys

TOKEN   = sys.argv[1]
BASE    = "http://localhost:3000"
SRC_ID  = sys.argv[2]

print(f"Ingestando fuente {SRC_ID}...")
with httpx.stream(
    "POST", f"{BASE}/api/sources/{SRC_ID}/ingest",
    headers={"Authorization": f"Bearer {TOKEN}", "Accept": "text/event-stream"},
    timeout=300.0,
) as r:
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
            print(f"  Escaneados: {d.get('total', '?')} ficheros")
        elif t == "progress":
            msg = d.get("message", "")
            cur = d.get("current", "")
            tot = d.get("total", "")
            if msg:
                print(f"  {msg} ({cur}/{tot})")
        elif t == "done":
            print("  Ingesta completada OK.")
            sys.exit(0)
        elif t == "error":
            print(f"  ERROR: {evt}", file=sys.stderr)
            sys.exit(1)
