import { useEffect, useState } from "react";
import { getSources } from "../../api/sources.js";

export default function IngestionProgress({ sourceId, onDone }) {
  const [progress, setProgress] = useState({ current: 0, total: 0, file: "" });
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("seekpal_token");
    const url = `/api/sources/${sourceId}/ingest`;

    const xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "text/event-stream");

    let buffer = "";
    xhr.onprogress = () => {
      const newData = xhr.responseText.slice(buffer.length);
      buffer = xhr.responseText;

      const lines = newData.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "progress") {
            setProgress({ current: event.current, total: event.total, file: event.file });
          } else if (event.type === "done") {
            setDone(true);
            // Reload source to get updated fileCount
            getSources().then((r) => {
              const updated = (r.data.data || []).find((s) => s._id === sourceId);
              if (updated) onDone(updated);
            });
          } else if (event.type === "error") {
            setError(event.message);
          }
        } catch {
          // ignore parse errors
        }
      }
    };

    xhr.send();
    return () => xhr.abort();
  }, [sourceId]);

  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  if (error) {
    return (
      <div className="mt-3 p-3 rounded-xl bg-red-50 border border-red-100 text-xs text-red-600">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-2">
      <div className="flex justify-between text-xs text-slate-500">
        <span className="truncate max-w-xs">{done ? "¡Ingesta completada!" : (progress.file || "Iniciando…")}</span>
        <span className="font-medium ml-2 flex-shrink-0">
          {progress.current}/{progress.total} ({pct}%)
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${done ? "bg-emerald-500" : "bg-indigo-500"}`}
          style={{ width: `${done ? 100 : pct}%` }}
        />
      </div>
    </div>
  );
}
