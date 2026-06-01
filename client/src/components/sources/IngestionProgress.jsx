import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getSources, pauseIngest, resumeIngest, cancelIngest, getIngestProgress } from "../../api/sources.js";
import { Search, Brain, Pause, Play, X } from "lucide-react";

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export default function IngestionProgress({ sourceId, onDone }) {
  const { t } = useTranslation();

  // "connecting" | "reconnecting" | "scanning" | "extracting" | "embedding"
  // | "indexing" | "paused" | "done"
  const [phase, setPhase] = useState("connecting");

  const [scanProgress,    setScanProgress]    = useState({ current: 0, total: 0, file: "" });
  const [extractProgress, setExtractProgress] = useState({ current: 0, total: 0, file: "" });
  const [indexProgress,   setIndexProgress]   = useState({ current: 0, total: 0, file: "" });
  const [embedProgress,   setEmbedProgress]   = useState({ current: 0, total: 0 });

  // Marca de agua: ficheros "procesados" que nunca retrocede aunque cambien
  // las fases. Se calcula como max(extractProgress, indexProgress).
  const [filesWatermark, setFilesWatermark] = useState(0);

  const [error,      setError]      = useState(null);
  const [paused,     setPaused]     = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);

  const doneRef        = useRef(false);
  const pollRef        = useRef(null);
  const startTimeRef   = useRef(Date.now());
  const tickRef        = useRef(null);
  const activePhaseRef = useRef("scanning");
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

  // Vuelca un snapshot de progreso del servidor sobre el estado del componente.
  // Permite que un cliente que reconecta (recibio 409) reconstruya las barras
  // reales en vez de quedarse en la barra indeterminada de "reconnecting".
  function applySnapshot(snap) {
    if (!snap) return;
    if (snap.scan)    setScanProgress({ current: snap.scan.current, total: snap.scan.total, file: snap.scan.file });
    if (snap.extract) setExtractProgress({ current: snap.extract.current, total: snap.extract.total, file: snap.extract.file });
    if (snap.index)   setIndexProgress({ current: snap.index.current, total: snap.index.total, file: snap.index.file });
    if (snap.embed)   setEmbedProgress({ current: snap.embed.current, total: snap.embed.total });
    const wm = Math.max(snap.extract?.current || 0, snap.index?.current || 0);
    setFilesWatermark((w) => Math.max(w, wm));
    setPaused(!!snap.paused);
    if (["scanning", "extracting", "embedding", "indexing"].includes(snap.phase)) {
      activePhaseRef.current = snap.phase;
      setPhase(snap.paused ? "paused" : snap.phase);
    }
  }

  async function pollOnce() {
    try {
      const r = await getIngestProgress(sourceId);
      const snap = r.data.data;

      if (!snap || snap.active === false) {
        clearInterval(pollRef.current);
        if (snap && snap.phase === "error") {
          setError(snap.error || t("ingest.error", { message: "Ingestion failed" }));
          return;
        }
        // done / cancelled / snapshot ausente → cerrar y refrescar la fuente
        markDone();
        try {
          const rs = await getSources();
          const updated = (rs.data.data || []).find((s) => s._id === sourceId);
          if (updated) onDone(updated);
        } catch { /* ignore */ }
        return;
      }

      // Ingesta viva: aplicar el progreso real (sale del modo indeterminado)
      applySnapshot(snap);
    } catch { /* ignore transient errors */ }
  }

  function startPolling() {
    // Sondeo inmediato para recuperar el progreso real cuanto antes (sin
    // esperar al primer tick de 2s, que dejaba la barra indeterminada visible).
    pollOnce();
    pollRef.current = setInterval(pollOnce, 2000);
  }

  useEffect(() => {
    mountedRef.current = true;

    const token = localStorage.getItem("seekpal_token");
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/sources/${sourceId}/ingest`, true);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "text/event-stream");

    let processedLen = 0;
    let partialLine = "";

    xhr.onprogress = () => {
      const newData = xhr.responseText.slice(processedLen);
      processedLen = xhr.responseText.length;

      const chunk = partialLine + newData;
      const lines = chunk.split("\n");
      partialLine = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const ev = JSON.parse(line.slice(6));

          if (ev.type === "scanning") {
            setPhase("scanning"); activePhaseRef.current = "scanning";

          } else if (ev.type === "progress") {
            setScanProgress({ current: ev.current, total: ev.total, file: ev.file });

          } else if (ev.type === "extracting_progress") {
            setPhase("extracting"); activePhaseRef.current = "extracting";
            setExtractProgress({ current: ev.current, total: ev.total, file: ev.file });
            setFilesWatermark((w) => Math.max(w, ev.current));

          } else if (ev.type === "embedding_start") {
            setPhase("embedding"); activePhaseRef.current = "embedding";
            setExtractProgress((p) => ({ ...p, total: ev.total }));
            setEmbedProgress({ current: 0, total: 0 });

          } else if (ev.type === "embedding_progress") {
            setEmbedProgress({ current: ev.current, total: ev.total });

          } else if (ev.type === "indexing_progress") {
            setPhase("indexing"); activePhaseRef.current = "indexing";
            setIndexProgress({ current: ev.current, total: ev.total, file: ev.file });
            setFilesWatermark((w) => Math.max(w, ev.current));

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
      if (!mountedRef.current) return;
      if (!doneRef.current) {
        // 409 = ingesta ya en progreso en el backend (usuario volvió a la página).
        // En lugar de reiniciar, entrar en modo polling mostrando "en progreso".
        if (xhr.status === 409) {
          setPhase("reconnecting");
        } else {
          const aiPhases = ["extracting", "embedding", "indexing"];
          setPhase((prev) =>
            aiPhases.includes(prev) || prev === "processing"
              ? activePhaseRef.current
              : prev
          );
        }
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

  // ── Cálculos de progreso ────────────────────────────────────────────────

  const isDone         = phase === "done";
  const isConnecting   = phase === "connecting";
  const isReconnecting = phase === "reconnecting";
  const isScanning     = phase === "scanning";
  const isActive       = !isDone && !isConnecting;

  // Barra 1: escaneo de ficheros
  const scanPct = scanProgress.total > 0
    ? Math.round((scanProgress.current / scanProgress.total) * 100) : 0;

  // Barra 2: proceso IA — usamos la marca de agua (nunca retrocede)
  const aiTotal   = extractProgress.total || indexProgress.total || 0;
  // Progreso real = ficheros completados (indexados). Si no hay datos de index
  // aún, usar la marca de agua (ficheros extraídos) como aproximación.
  const aiDone    = indexProgress.current > 0 ? indexProgress.current : filesWatermark;
  const aiPct     = isDone ? 100
                  : aiTotal > 0 ? Math.round((aiDone / aiTotal) * 100)
                  : 0;

  const showAIBar = !isConnecting && !isReconnecting && !isScanning || isDone;

  // Nombre de fichero activo para el sub-texto. Durante embedding usamos el último
  // fichero extraído (extractProgress.file no se borra al cambiar de fase).
  const currentFile = phase === "indexing" ? indexProgress.file : extractProgress.file;

  const phaseLabel = (() => {
    if (paused)                return t("ingest.phase.paused");
    if (phase === "embedding") return t("ingest.phase.embedding");
    if (phase === "indexing")  return t("ingest.phase.index");
    return t("ingest.phase.extracting");
  })();

  const chunkDetail = phase === "embedding" && embedProgress.total > 0
    ? ` · ${embedProgress.current}/${embedProgress.total} chunks`
    : "";

  const aiSubtext = isDone || paused || isReconnecting || !currentFile
    ? null
    : `${currentFile} — ${phaseLabel}${chunkDetail}`;

  return (
    <div className="mt-4 space-y-3">

      {/* ── Barra 1: Escaneo de ficheros ─────────────────────────────── */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1.5">
            <Search size={11} className={(isConnecting || isScanning) ? "animate-pulse" : ""} />
            {t("ingest.phase.scan")}
          </span>
          {!isConnecting && !isReconnecting && (!isScanning || scanProgress.total > 0) && (
            <span className="font-medium tabular-nums ml-2 flex-shrink-0">
              {isDone
                ? t("ingest.fileCount", { count: scanProgress.total })
                : t("ingest.progress", { current: scanProgress.current, total: scanProgress.total, pct: scanPct })}
            </span>
          )}
        </div>
        <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
          {isConnecting || (isScanning && scanProgress.total === 0) ? (
            <div className="h-full w-1/3 rounded-full bg-indigo-400 animate-[scanning_1.2s_ease-in-out_infinite]" />
          ) : (
            <div
              className="h-full rounded-full transition-all duration-300 bg-indigo-500"
              style={{ width: `${!isScanning || isDone || isReconnecting ? 100 : scanPct}%` }}
            />
          )}
        </div>
      </div>

      {/* ── Barra 2: Proceso IA ──────────────────────────────────────── */}
      {(showAIBar || isReconnecting) && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span className="flex items-center gap-1.5">
              <Brain size={11} />
              {isReconnecting ? t("ingest.reconnecting", "En progreso...") : t("ingest.phase.aiProcessing")}
            </span>

            {!isReconnecting && aiTotal > 0 && (
              <span className="font-medium tabular-nums ml-2 flex-shrink-0">
                {isDone
                  ? t("ingest.fileCount", { count: aiTotal })
                  : `${t("ingest.file", "Fichero")} ${aiDone} / ${aiTotal}`}
              </span>
            )}
          </div>

          <div className="h-1.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            {isReconnecting ? (
              <div className="h-full w-1/2 rounded-full bg-indigo-400 animate-[scanning_1.2s_ease-in-out_infinite]" />
            ) : (
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  isDone ? "bg-emerald-500" : paused ? "bg-amber-500" : "bg-indigo-500"
                }`}
                style={{ width: `${isDone ? 100 : aiPct}%` }}
              />
            )}
          </div>

          {aiSubtext && (
            <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate" title={aiSubtext}>
              ↳ {aiSubtext}
            </p>
          )}
        </div>
      )}

      {/* ── Controles + cronómetro ────────────────────────────────────── */}
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
