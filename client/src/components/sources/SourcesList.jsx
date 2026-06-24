import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Trash2, Play, Clock, CheckCircle, AlertCircle, Loader, RefreshCw, Scan, Brain } from "lucide-react";
import IngestionProgress from "./IngestionProgress.jsx";
import Button from "../ui/Button.jsx";
import { toggleAutoIndex } from "../../api/sources.js";

function formatSize(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} Bytes`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function formatDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
}

function formatDuration(secs) {
  if (!secs) return null;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function SourcesList({ sources, onDelete, onUpdate }) {
  const { t } = useTranslation();
  // Si al montar la lista ya hay una fuente en proceso (el usuario volvió a la
  // página mientras indexaba), mostrar el componente de progreso inmediatamente.
  const [ingesting, setIngesting] = useState(
    () => sources.find((s) => s.status === "scanning")?._id ?? null
  );
  const [ingestForce, setIngestForce] = useState(true);
  const [togglingId, setTogglingId] = useState(null);

  const STATUS_CONFIG = {
    idle:     { icon: Clock,        color: "text-slate-400",            bg: "bg-slate-100 dark:bg-slate-700", label: t("sources.status.idle") },
    scanning: { icon: Loader,       color: "text-brand",                bg: "bg-brand-soft",                  label: t("sources.status.scanning") },
    indexing: { icon: Brain,        color: "text-brand",                bg: "bg-brand-soft",                  label: t("sources.status.indexing") },
    done:     { icon: CheckCircle,  color: "text-success",              bg: "bg-success-soft",                label: t("sources.status.done") },
    error:    { icon: AlertCircle,  color: "text-danger",               bg: "bg-danger-soft",                 label: t("sources.status.error") },
  };

  async function handleToggleAutoIndex(source) {
    setTogglingId(source._id);
    try {
      const res = await toggleAutoIndex(source._id);
      onUpdate(res.data.data);
    } finally {
      setTogglingId(null);
    }
  }

  if (!sources.length) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-dashed border-slate-200 dark:border-slate-600 rounded-2xl p-16 text-center">
        <p className="text-slate-400 dark:text-slate-500 text-sm">{t("sources.emptyState")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {sources.map((source, idx) => {
        // When scanning with files already present → embedding phase (not initial scan)
        const effectiveStatus =
          source.status === "scanning" && (source.fileCount ?? 0) > 0 ? "indexing" : source.status;
        const cfg = STATUS_CONFIG[effectiveStatus] || STATUS_CONFIG.idle;
        const Icon = cfg.icon;
        const isIngesting = ingesting === source._id;

        return (
          <div key={source._id} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 shadow-card reveal-up" style={{ "--stagger": idx }}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between lg:gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-slate-800 dark:text-slate-100 truncate">{source.name}</h3>
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                    <Icon size={11} className={source.status === "scanning" ? "animate-spin" : effectiveStatus === "indexing" ? "animate-pulse" : ""} />
                    {cfg.label}
                  </span>
                </div>
                <p className="text-slate-400 dark:text-slate-500 text-xs font-mono truncate">{source.path}</p>
                {/* Cada dato es atómico (no se parte "68 indexados"); con gap-y
                    las secciones envuelven limpias si no caben en una línea. */}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-2 text-xs text-slate-400 dark:text-slate-500">
                  <span>{t("sources.fileCount", { count: source.fileCount ?? 0 })}</span>
                  {source.lastIngested && (
                    <span>
                      {t("sources.lastIngest", { date: formatDate(source.lastIngested) })}
                      {formatDuration(source.lastIngestDurationSecs) && ` (${formatDuration(source.lastIngestDurationSecs)})`}
                    </span>
                  )}
                  {source.lastIngested && (<>
                    <span className="text-success font-medium">{t("sources.indexed", { count: source.indexedCount ?? 0 })}</span>
                    <span>{t("sources.empty", { count: source.skippedCount ?? 0 })}</span>
                    <span className={(source.failedCount ?? 0) > 0 ? "text-danger font-medium" : ""}>{t("sources.notIndexed", { count: source.failedCount ?? 0 })}</span>
                  </>)}
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
                <Button
                  variant={source.autoIndex ? "brand" : "neutral"}
                  onClick={() => handleToggleAutoIndex(source)}
                  disabled={togglingId === source._id}
                  title={source.autoIndex ? t("sources.autoIndexOn") : t("sources.autoIndexOff")}
                >
                  <RefreshCw size={14} className={togglingId === source._id ? "animate-spin" : ""} />
                  {t("sources.auto")}
                </Button>

                <Button
                  variant="neutral"
                  onClick={() => { setIngestForce(false); setIngesting(source._id); }}
                  disabled={isIngesting || source.status === "scanning"}
                  title={t("sources.updateTooltip")}
                >
                  <Scan size={14} />
                  {t("sources.update")}
                </Button>

                <Button
                  variant="brand"
                  onClick={() => { setIngestForce(true); setIngesting(source._id); }}
                  disabled={isIngesting || source.status === "scanning"}
                  title={t("sources.ingestAllTooltip")}
                >
                  <Play size={14} />
                  {t("sources.ingestAll")}
                </Button>

                <Button
                  size="sm"
                  className="!p-1.5 !bg-red-500 !text-white hover:!bg-red-600"
                  onClick={() => onDelete(source._id)}
                  title={t("sources.deleteTooltip")}
                >
                  <Trash2 size={16} />
                </Button>
              </div>
            </div>

            {isIngesting && (
              <IngestionProgress
                sourceId={source._id}
                force={ingestForce}
                onDone={(updated) => { setIngesting(null); onUpdate(updated); }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
