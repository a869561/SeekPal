import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Trash2, PlayCircle, Clock, CheckCircle, AlertCircle, Loader, RefreshCw } from "lucide-react";
import IngestionProgress from "./IngestionProgress.jsx";
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

export default function SourcesList({ sources, onDelete, onUpdate }) {
  const { t } = useTranslation();
  const [ingesting, setIngesting] = useState(null);
  const [togglingId, setTogglingId] = useState(null);

  const STATUS_CONFIG = {
    idle:     { icon: Clock,        color: "text-slate-400",   bg: "bg-slate-100 dark:bg-slate-700",    label: t("sources.status.idle") },
    scanning: { icon: Loader,       color: "text-indigo-500",  bg: "bg-indigo-50 dark:bg-indigo-950",   label: t("sources.status.scanning") },
    done:     { icon: CheckCircle,  color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950", label: t("sources.status.done") },
    error:    { icon: AlertCircle,  color: "text-red-500",     bg: "bg-red-50 dark:bg-red-950",         label: t("sources.status.error") },
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
      {sources.map((source) => {
        const cfg = STATUS_CONFIG[source.status] || STATUS_CONFIG.idle;
        const Icon = cfg.icon;
        const isIngesting = ingesting === source._id;

        return (
          <div key={source._id} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-slate-800 dark:text-slate-100 truncate">{source.name}</h3>
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                    <Icon size={11} className={source.status === "scanning" ? "animate-spin" : ""} />
                    {cfg.label}
                  </span>
                </div>
                <p className="text-slate-400 dark:text-slate-500 text-xs font-mono truncate">{source.path}</p>
                <div className="flex items-center gap-4 mt-2 text-xs text-slate-400 dark:text-slate-500">
                  <span>{t("sources.fileCount", { count: source.fileCount ?? 0 })}</span>
                  <span>{t("sources.lastIngest", { date: formatDate(source.lastIngested) })}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => handleToggleAutoIndex(source)}
                  disabled={togglingId === source._id}
                  title={source.autoIndex ? t("sources.autoIndexOn") : t("sources.autoIndexOff")}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition disabled:opacity-40 ${
                    source.autoIndex
                      ? "bg-emerald-50 dark:bg-emerald-950 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900"
                      : "bg-slate-100 dark:bg-slate-700 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600"
                  }`}
                >
                  <RefreshCw size={14} className={togglingId === source._id ? "animate-spin" : ""} />
                  {t("sources.auto")}
                </button>

                <button
                  onClick={() => setIngesting(source._id)}
                  disabled={isIngesting || source.status === "scanning"}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 hover:bg-indigo-100 dark:hover:bg-indigo-900 disabled:opacity-40 transition"
                >
                  <PlayCircle size={14} />
                  {t("sources.ingest")}
                </button>
                <button
                  onClick={() => onDelete(source._id)}
                  className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950 rounded-lg transition"
                  title={t("sources.deleteTooltip")}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>

            {isIngesting && (
              <IngestionProgress
                sourceId={source._id}
                onDone={(updated) => { setIngesting(null); onUpdate(updated); }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
