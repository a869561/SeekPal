import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getSources, pauseIngest, resumeIngest, cancelIngest } from "../../api/sources.js";
import { Search, Brain, Pause, Play, X } from "lucide-react";

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export default function IngestionProgress({ sourceId, onDone }) {
  const { t } = useTranslation();

  // "connecting" | "scanning" | "processing" | "extracting" | "embedding" | "indexing" | "paused" | "done"
  const [phase, setPhase] = useState("connecting");
  const [scanProgress,    setScanProgress]    = useState({ current: 0, total: 0, file: "" });
  const [extractProgress, setExtractProgress] = useState({ current: 0, total: 0, file: "" });
  const [indexProgress,   setIndexProgress]   = useState({ current: 0, total: 0, file: "" });
  const [embedProgress,   setEmbedProgress]   = useState({ current: 0, total: 0 });
  const [error,    setError]    = useState(null);
  const [paused,   setPaused]   = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);

  const doneRef        = useRef(false);
  const pollRef        = useRef(null);
  const startTimeRef   = useRef(Date.now());
  const tickRef        = useRef(null);
  const activePhaseRef = useRef("scanning");
  // True mientras el componente esta montado. Evita que onloadend arranque
  // polling huerfano tras un xhr.abort() del cleanup (el polling quedaria
  // corriendo cada 3s hasta agotar los 400 intentos = ~20 min).
  const mountedRef     = useRef(true);

  useEffect(() => {
    tickRef.current = setInterval(() => {
      if (!doneRef.current && !paused)
        setElapsedSec(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(tickRef.current);
  }, [paused]);

  function markDone() {
    doneRef.current = true;
    clearInterval(tickRef.current);
    setElapsedSec(Math.floor((Date.now() - startTimeRef.current) / 1000));
    setPhase("done");
  }

  function startPolling() {
    let attempts = 0;
    pollRef.current = setInterval(async () => {
      if (++attempts > 400) { clearInterval(pollRef.current); return; }
      try {
        const r = await getSources();
        const s = (r.data.data || []).find((x) => x._id === sourceId);
        if (!s || s.status !== "scanning") {
          clearInterval(pollRef.current);
          if (s?.status === "done") { markDone(); onDone(s); }
          else if (s?.status === "error") setError(t("ingest.error", { message: "Ingestion failed" }));
        }
      } catch { /* ignore transient errors */ }
    }, 3000);
  }

  useEffect(() => {
    mountedRef.current = true;

    const token = localStorage.getItem("seekpal_token");
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/sources/${sourceId}/ingest`, true);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "text/event-stream");

    // Solo trackear el offset, no copiar el responseText acumulado en una
    // variable: en ingestas largas (10k+ ficheros, MB de eventos) duplicar
    // el string en cada onprogress hace crecer la memoria del navegador.
    let processedLen = 0;
    let partialLine = "";

    xhr.onprogress = () => {
      const newData = xhr.responseText.slice(processedLen);
      processedLen = xhr.responseText.length;

      const chunk = partialLine + newData;
      const lines = chunk.split("\n");
      // La ultima entrada puede ser una linea incompleta — la guardamos
      // para concatenar con el siguiente fragmento.
      partialLine = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const ev = JSON.parse(line.slice(6));
          if (ev.type === "scanning") {
            setPhase("scanning"); activePhaseRef.current = "scanning";

          } else if (ev.type === "progress") {
            setPhase("processing"); activePhaseRef.current = "processing";
            setScanProgress({ current: ev.current, total: ev.total, file: ev.file });

          } else if (ev.type === "extracting_progress") {
            setPhase("extracting"); activePhaseRef.current = "extracting";
            setExtractProgress({ current: ev.current, total: ev.total, file: ev.file });

          } else if (ev.type === "embedding_start") {
            setPhase("embedding"); activePhaseRef.current = "embedding";
            setExtractProgress((p) => ({ ...p, total: ev.total }));
            setEmbedProgress({ current: 0, total: 0 });

          } else if (ev.type === "embedding_progress") {
            setEmbedProgress({ current: ev.current, total: ev.total });

          } else if (ev.type === "indexing_progress") {
            setPhase("indexing"); activePhaseRef.current = "indexing";
            setIndexProgress({ current: ev.current, total: ev.total, file: ev.file });

          } else if (ev.type === "paused") {
            setPaused(true); setPhase("paused");

          } else if (ev.type === "resumed") {
            setPaused(false); setPhase(activePhaseRef.current);

          } else if (ev.type === "cancelled") {
            markDone();

          } else if (ev.type === "done") {
            markDone();
            getSources().then((r) => {
              const updated = (r.data.data || []).find((s) => s._id === sourceId);
              if (updated) onDone(updated);
            });

          } else if (ev.type === "error") {
            setError(ev.message);
          }
        } catch { /* ignore parse errors */ }
      }
    };

    xhr.onloadend = () => {
      // Si el componente ya se desmonto, no levantar polling: el cleanup del
      // useEffect dispara xhr.abort() que llega aqui despues de limpiar.
      if (!mountedRef.current) return;
      if (!doneRef.current) {
        const aiPhases = ["extracting", "embedding", "indexing"];
        setPhase((prev) => (aiPhases.includes(prev) || prev === "processing" ? activePhaseRef.current : prev));
        startPolling();
      }
    };

    xhr.send();
    return () => {
      mountedRef.current = false;
      xhr.abort();
      clearInterval(pollRef.current);
    };
  }, [sourceId]);

  async function handlePause() {
    try { await pauseIngest(sourceId); } catch { /* ignore */ }
    setPaused(true); setPhase("paused");
  }
  async function handleResume() {
    try { await resumeIngest(sourceId); } catch { /* ignore */ }
    setPaused(false); setPhase(activePhaseRef.current);
  }
  async function handleCancel() {
    try { await cancelIngest(sourceId); } catch { /* ignore */ }
    markDone();
    getSources().then((r) => {
      const updated = (r.data.data || []).find((s) => s._id === sourceId);
      if (updated) onDone(updated);
    });
  }

  if (error) {
    return (
      <div className="mt-3 p-3 rounded-xl bg-red-50 dark:bg-red-950 border border-red-100 dark:border-red-900 text-xs text-red-600 dark:text-red-400">
        {t("ingest.error", { message: error })}
      </div>
    );
  }

  const isDone       = phase === "done";
  const isConnecting = phase === "connecting";
  const isScanning   = phase === "scanning";
  const isAI = ["extracting", "embedding", "indexing", "paused"].includes(phase);
  const isActive = !isDone && !isConnecting;

  const scanPct = scanProgress.total > 0
    ? Math.round((scanProgress.current / scanProgress.total) * 100) : 0;

  // Progreso de la barra de IA según sub-fase
  const embedPct = embedProgress.total > 0
    ? Math.round((embedProgress.current / embedProgress.total) * 100) : 0;

  const aiTotal   = phase === "extracting" ? extractProgress.total
                  : phase === "embedding"  ? embedProgress.total
                  : indexProgress.total || extractProgress.total;
  const aiCurrent = phase === "extracting" ? extractProgress.current
                  : phase === "embedding"  ? embedProgress.current
                  : indexProgress.current;
  const aiFile    = phase === "extracting" ? extractProgress.file : indexProgress.file;
  const aiPct     = phase === "embedding"  ? embedPct
                  : aiTotal > 0 ? Math.round((aiCurrent / aiTotal) * 100) : 0;

  const showAIBar  = isAI || isDone;
  // Barra animada solo si aún no hay datos de progreso
  const aiAnimated = !isDone && !paused && (
    (phase === "embedding"  && embedProgress.total === 0) ||
    (phase !== "embedding"  && aiTotal === 0)
  );

  const aiLabel =
    paused                 ? t("ingest.phase.paused")     :
    phase === "extracting" ? t("ingest.phase.extracting") :
    phase === "embedding"  ? t("ingest.phase.embedding")  :
    t("ingest.phase.index");

  return (
    <div className="mt-4 space-y-3">
      {/* Barra 1 — Escaneo de ficheros */}
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
            <div className="h-full rounded-full transition-all duration-300 bg-indigo-500"
                 style={{ width: `${showAIBar || isDone ? 100 : scanPct}%` }} />
          )}
        </div>
      </div>

      {/* Barra 2 — IA (extracción → vectorización → indexado) */}
      {showAIBar && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-violet-600 dark:text-violet-400">
            <span className="flex items-center gap-1.5">
              <Brain size={11} className={isDone || paused ? "" : "animate-pulse"} />
              {aiLabel}
            </span>
            {/* Contador: se muestra cuando hay datos deterministas */}
            {!aiAnimated && aiTotal > 0 && (
              <span className="font-medium tabular-nums ml-2 flex-shrink-0">
                {isDone
                  ? t("ingest.fileCount", { count: indexProgress.total || extractProgress.total })
                  : phase === "embedding"
                    ? t("ingest.embedProgress", { current: aiCurrent, total: aiTotal, pct: aiPct })
                    : t("ingest.progress", { current: aiCurrent, total: aiTotal, pct: aiPct })}
              </span>
            )}
          </div>

          <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            {aiAnimated ? (
              <div className="h-full w-full rounded-full bg-violet-400 animate-[scanning_1.2s_ease-in-out_infinite]" />
            ) : (
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  isDone ? "bg-emerald-500" : paused ? "bg-amber-500" : "bg-violet-500"
                }`}
                style={{ width: `${isDone ? 100 : aiPct}%` }}
              />
            )}
          </div>

          {/* Nombre del fichero en proceso */}
          {!isDone && !paused && aiFile && (
            <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate" title={aiFile}>
              {aiFile}
            </p>
          )}
        </div>
      )}

      {/* Controles + tiempo */}
      <div className="flex items-center justify-between">
        <p className={`text-xs font-medium ${isDone ? "text-emerald-600 dark:text-emerald-400" : "text-slate-400 dark:text-slate-500"}`}>
          {isDone ? `${t("ingest.done")} — ${formatDuration(elapsedSec)}` : formatDuration(elapsedSec)}
        </p>

        {isActive && (
          <div className="flex items-center gap-1.5">
            {paused ? (
              <button onClick={handleResume}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950 hover:bg-emerald-100 dark:hover:bg-emerald-900 transition-colors">
                <Play size={10} />{t("ingest.resume", "Reanudar")}
              </button>
            ) : (
              <button onClick={handlePause}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950 hover:bg-amber-100 dark:hover:bg-amber-900 transition-colors">
                <Pause size={10} />{t("ingest.pause", "Pausar")}
              </button>
            )}
            <button onClick={handleCancel}
              className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 hover:bg-red-100 dark:hover:bg-red-900 transition-colors">
              <X size={10} />{t("ingest.cancel", "Cancelar")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
