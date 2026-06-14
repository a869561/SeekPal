import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getSources, pauseIngest, resumeIngest, cancelIngest, getIngestProgress } from "../../api/sources.js";
import { Search, Brain, Pause, Play, X, ChevronDown, ChevronUp } from "lucide-react";
import Button from "../ui/Button.jsx";
import ProgressBar from "../ui/ProgressBar.jsx";

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

export default function IngestionProgress({ sourceId, onDone, force = true }) {
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
  // Mostrar/ocultar las barras de detalle. Por defecto visible; se recuerda en
  // localStorage para que la preferencia persista entre sesiones y refrescos.
  const [showDetails, setShowDetails] = useState(
    () => localStorage.getItem("seekpal_ingest_details") !== "0"
  );

  function toggleDetails() {
    setShowDetails((v) => {
      const nv = !v;
      localStorage.setItem("seekpal_ingest_details", nv ? "1" : "0");
      return nv;
    });
  }

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
    // Sembrar el cronómetro con la hora de inicio real del servidor: así el
    // tiempo transcurrido sobrevive a un F5 (antes el reloj rearrancaba de 0).
    if (snap.startedAt) startTimeRef.current = snap.startedAt;
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
    xhr.open("POST", `/api/sources/${sourceId}/ingest?force=${force}`, true);
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
      <div className="mt-3 p-3 rounded-xl bg-danger-soft border border-danger/20 text-xs text-danger">
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
  // filesWatermark es el máximo acumulado de extract+index: avanza per-file
  // durante extracción y nunca retrocede al cambiar de fase. Usarlo siempre
  // evita el salto atrás al iniciar indexado (index.current=1 < watermark=15)
  // y el bloqueo durante extracción de grupos 2+ (index.current queda obsoleto).
  const aiDone    = filesWatermark;
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

      {showDetails && (
      <>
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
        <ProgressBar
          indeterminate={isConnecting || (isScanning && scanProgress.total === 0)}
          value={!isScanning || isDone || isReconnecting ? 100 : scanPct}
          active={isScanning}
          tone="brand"
        />
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

          <ProgressBar
            indeterminate={isReconnecting}
            value={isDone ? 100 : aiPct}
            active={!isDone && !paused}
            tone={isDone ? "success" : "brand"}
          />

          {aiSubtext && (
            <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate" title={aiSubtext}>
              ↳ {aiSubtext}
            </p>
          )}
        </div>
      )}
      </>
      )}

      {/* ── Controles + cronómetro ────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className={`text-xs font-medium ${isDone ? "text-success" : "text-slate-400 dark:text-slate-500"}`}>
            {isDone ? `${t("ingest.done")} — ${formatDuration(elapsedSec)}` : formatDuration(elapsedSec)}
          </p>
          <button
            type="button"
            onClick={toggleDetails}
            className="flex items-center gap-0.5 text-[10px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            title={t("ingest.details", "Detalles")}
          >
            {t("ingest.details", "Detalles")}
            {showDetails ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
          </button>
        </div>

        {isActive && (
          <div className="flex items-center gap-1.5">
            {paused ? (
              <Button variant="brand" size="sm" onClick={handleResume}>
                <Play size={10} />{t("ingest.resume", "Reanudar")}
              </Button>
            ) : (
              <Button variant="neutral" size="sm" onClick={handlePause}>
                <Pause size={10} />{t("ingest.pause", "Pausar")}
              </Button>
            )}
            <Button variant="danger" size="sm" onClick={handleCancel}>
              <X size={10} />{t("ingest.cancel", "Cancelar")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
