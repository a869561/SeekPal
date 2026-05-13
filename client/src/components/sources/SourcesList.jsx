import { useState } from "react";
import { Trash2, PlayCircle, Clock, CheckCircle, AlertCircle, Loader } from "lucide-react";
import IngestionProgress from "./IngestionProgress.jsx";

const STATUS_CONFIG = {
  idle:     { icon: Clock,         color: "text-slate-400",  bg: "bg-slate-100",  label: "Sin ingestar" },
  scanning: { icon: Loader,        color: "text-indigo-500", bg: "bg-indigo-50",  label: "Escaneando…" },
  done:     { icon: CheckCircle,   color: "text-emerald-500",bg: "bg-emerald-50", label: "Completado" },
  error:    { icon: AlertCircle,   color: "text-red-500",    bg: "bg-red-50",     label: "Error" },
};

function formatSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function formatDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleString("es-ES", { dateStyle: "short", timeStyle: "short" });
}

export default function SourcesList({ sources, onDelete, onUpdate }) {
  const [ingesting, setIngesting] = useState(null); // sourceId currently ingesting

  if (!sources.length) {
    return (
      <div className="bg-white border border-dashed border-slate-200 rounded-2xl p-16 text-center">
        <p className="text-slate-400 text-sm">No hay fuentes. Añade un directorio para empezar.</p>
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
          <div key={source._id} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              {/* Info */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-slate-800 truncate">{source.name}</h3>
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                    <Icon size={11} className={source.status === "scanning" ? "animate-spin" : ""} />
                    {cfg.label}
                  </span>
                </div>
                <p className="text-slate-400 text-xs font-mono truncate">{source.path}</p>
                <div className="flex items-center gap-4 mt-2 text-xs text-slate-400">
                  <span>{source.fileCount ?? 0} ficheros</span>
                  <span>Última ingesta: {formatDate(source.lastIngested)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => setIngesting(source._id)}
                  disabled={isIngesting || source.status === "scanning"}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-indigo-50 text-indigo-600 hover:bg-indigo-100 disabled:opacity-40 transition"
                >
                  <PlayCircle size={14} />
                  Ingestar
                </button>
                <button
                  onClick={() => onDelete(source._id)}
                  className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
                  title="Eliminar fuente"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>

            {/* Progress bar */}
            {isIngesting && (
              <IngestionProgress
                sourceId={source._id}
                onDone={(updated) => {
                  setIngesting(null);
                  onUpdate(updated);
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
