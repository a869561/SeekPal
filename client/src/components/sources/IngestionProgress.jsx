import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getSources } from "../../api/sources.js";
import { Search, Brain } from "lucide-react";

export default function IngestionProgress({ sourceId, onDone }) {
  const { t } = useTranslation();
  const [phase, setPhase] = useState("connecting"); // connecting | scanning | processing | indexing | done
  const [scanProgress, setScanProgress] = useState({ current: 0, total: 0, file: "" });
  const [indexProgress, setIndexProgress] = useState({ current: 0, total: 0, file: "" });
  const [error, setError] = useState(null);

  const doneRef = useRef(false);
  const pollRef = useRef(null);

  function startPolling() {
    let attempts = 0;
    pollRef.current = setInterval(async () => {
      attempts++;
      if (attempts > 400) { // max ~20 min
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
            setScanProgress({ current: event.current, total: event.total, file: event.file });
          } else if (event.type === "indexing_progress") {
            setPhase("indexing");
            setIndexProgress({ current: event.current, total: event.total, file: event.file });
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

    // SSE connection ended — backend task continues running independently.
    xhr.onloadend = () => {
      if (!doneRef.current) {
        setPhase((prev) => (prev === "processing" || prev === "indexing" ? "indexing" : prev));
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

  const isDone = phase === "done";
  const isConnecting = phase === "connecting";
  const isScanning = phase === "scanning";
  const isProcessing = phase === "processing";
  const isIndexing = phase === "indexing";

  const scanPct = scanProgress.total > 0
    ? Math.round((scanProgress.current / scanProgress.total) * 100)
    : 0;
  const indexPct = indexProgress.total > 0
    ? Math.round((indexProgress.current / indexProgress.total) * 100)
    : 0;

  // Phase 2 bar is shown as soon as we enter the indexing phase
  const showIndexBar = isIndexing || isDone;
  // Phase 2 has no data yet (SSE dropped before indexing events arrived)
  const indexingBlind = isIndexing && indexProgress.total === 0;

  return (
    <div className="mt-4 space-y-3">
      {/* Phase 1 — File scanning */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <Search size={11} className={(isConnecting || isScanning) ? "animate-pulse" : ""} />
            {t("ingest.phase.scan")}
          </span>
          {!isConnecting && !isScanning && (
            <span className="font-medium tabular-nums ml-2 flex-shrink-0">
              {isDone
                ? t("ingest.fileCount", { count: scanProgress.total })
                : t("ingest.progress", { current: scanProgress.current, total: scanProgress.total, pct: scanPct })}
            </span>
          )}
        </div>
        <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
          {isConnecting || isScanning ? (
            <div className="h-full w-1/3 rounded-full bg-indigo-400 animate-[scanning_1.2s_ease-in-out_infinite]" />
          ) : (
            <div
              className={`h-full rounded-full transition-all duration-300 ${isDone || showIndexBar ? "bg-indigo-500" : "bg-indigo-500"}`}
              style={{ width: `${showIndexBar || isDone ? 100 : scanPct}%` }}
            />
          )}
        </div>
      </div>

      {/* Phase 2 — AI indexing (appears once scan is done) */}
      {showIndexBar && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-violet-600 dark:text-violet-400">
            <span className="flex items-center gap-1.5">
              <Brain size={11} className={isDone ? "" : "animate-pulse"} />
              {t("ingest.phase.index")}
            </span>
            {!indexingBlind && (
              <span className="font-medium tabular-nums ml-2 flex-shrink-0">
                {isDone
                  ? t("ingest.fileCount", { count: indexProgress.total || scanProgress.total })
                  : t("ingest.progress", { current: indexProgress.current, total: indexProgress.total, pct: indexPct })}
              </span>
            )}
          </div>
          <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            {indexingBlind ? (
              <div className="h-full w-full rounded-full bg-violet-400 animate-[scanning_1.2s_ease-in-out_infinite]" />
            ) : (
              <div
                className={`h-full rounded-full transition-all duration-300 ${isDone ? "bg-emerald-500" : "bg-violet-500"}`}
                style={{ width: `${isDone ? 100 : indexPct}%` }}
              />
            )}
          </div>
        </div>
      )}

      {isDone && (
        <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
          {t("ingest.done")}
        </p>
      )}
    </div>
  );
}
