import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getSources } from "../../api/sources.js";
import { Search } from "lucide-react";

export default function IngestionProgress({ sourceId, onDone }) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState("connecting");
  const [progress, setProgress] = useState({ current: 0, total: 0, file: "" });
  const [error, setError] = useState(null);

  const doneRef = useRef(false);
  const pollRef = useRef(null);

  function startPolling() {
    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts++;
      if (attempts > 60) { // max ~3 min
        clearInterval(pollRef.current);
        return;
      }
      try {
        const r = await getSources();
        const s = (r.data.data || []).find((x) => x._id === sourceId);
        if (!s || s.status !== "scanning") {
          clearInterval(pollRef.current);
          if (s?.status === "done") {
            doneRef.current = true;
            setPhase("done");
            onDone(s);
          } else if (s?.status === "error") {
            setError(t("ingest.error", { message: "Ingestion failed" }));
          }
        }
      } catch {
        // ignore transient fetch errors
      }
    }, 3000);
  }

  useEffect(() => {
    const token = localStorage.getItem("seekpal_token");
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/sources/${sourceId}/ingest`, true);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "text/event-stream");

    let buffer = "";

    xhr.onprogress = () => {
      const newData = xhr.responseText.slice(buffer.length);
      buffer = xhr.responseText;

      for (const line of newData.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "scanning") {
            setPhase("scanning");
          } else if (event.type === "progress") {
            setPhase("processing");
            setProgress({ current: event.current, total: event.total, file: event.file });
          } else if (event.type === "done") {
            doneRef.current = true;
            setPhase("done");
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

    // SSE connection ended — if we never got "done", poll until status resolves
    xhr.onloadend = () => {
      if (!doneRef.current) {
        startPolling();
      }
    };

    xhr.send();

    return () => {
      xhr.abort();
      clearInterval(pollRef.current);
    };
  }, [sourceId]);

  if (error) {
    return (
      <div className="mt-3 p-3 rounded-xl bg-red-50 dark:bg-red-950 border border-red-100 dark:border-red-900 text-xs text-red-600 dark:text-red-400">
        {t("ingest.error", { message: error })}
      </div>
    );
  }

  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;
  const isDone = phase === "done";
  const isScanning = phase === "scanning" || phase === "connecting";

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        {isScanning ? (
          <span className="flex items-center gap-1.5">
            <Search size={11} className="animate-pulse" />
            {t("ingest.searching")}
          </span>
        ) : isDone ? (
          <span className="text-emerald-600 dark:text-emerald-400 font-medium">{t("ingest.done")}</span>
        ) : (
          <span className="truncate max-w-xs">{progress.file || t("ingest.processing")}</span>
        )}

        {!isScanning && (
          <span className="font-medium ml-2 flex-shrink-0 tabular-nums">
            {isDone
              ? t("ingest.fileCount", { count: progress.total })
              : t("ingest.progress", { current: progress.current, total: progress.total, pct })}
          </span>
        )}
      </div>

      <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
        {isScanning ? (
          <div className="h-full w-1/3 rounded-full bg-indigo-400 animate-[scanning_1.2s_ease-in-out_infinite]" />
        ) : (
          <div
            className={`h-full rounded-full transition-all duration-300 ${isDone ? "bg-emerald-500" : "bg-indigo-500"}`}
            style={{ width: `${isDone ? 100 : pct}%` }}
          />
        )}
      </div>
    </div>
  );
}
