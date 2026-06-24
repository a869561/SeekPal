import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, HardDrive, Download, Trash2, Check, Lock, X, RefreshCw } from "lucide-react";
import { getModels, pullModel, getModelPullStatus, deleteModel } from "../../api/system.js";
import Button from "../ui/Button.jsx";
import CollapsibleHeader from "../ui/CollapsibleHeader.jsx";
import useCollapsed from "../../hooks/useCollapsed.js";

function formatSize(bytes) {
  if (!bytes) return "";
  const gb = bytes / 1e9;
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  return `${Math.round(bytes / 1e6)} MB`;
}

// Nombre compacto para mostrar: si pegas una URL de Hugging Face (o un repo
// hf.co/usuario/repo) el id es larguísimo, así que nos quedamos con la última
// parte significativa (el nombre del modelo). El id completo va en el title.
function shortModelName(id) {
  if (!id) return id;
  const clean = id.replace(/^https?:\/\//, "").replace(/^(huggingface\.co|hf\.co)\//, "");
  const parts = clean.split("/").filter(Boolean);
  return parts.length ? parts[parts.length - 1] : id;
}

// Razón legible de un fallo del POST (nombre inválido 400, descarga en curso
// 409…). El motivo de un pull que falla durante la descarga llega aparte por
// pull-status (st.error, el mensaje real de Ollama).
function apiErrorReason(err) {
  return err?.response?.data?.message || err?.response?.data?.detail || null;
}

const CATEGORY_KEY = {
  vision: "modelsCard.catVision",
  llm: "modelsCard.catLlm",
  audio: "modelsCard.catAudio",
  ocr: "modelsCard.catOcr",
  pdf: "modelsCard.catPdf",
  otro: "modelsCard.catOther",
};

export default function ModelsCard() {
  const { t } = useTranslation();
  const [models, setModels] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pulling, setPulling] = useState(null); // id del modelo descargándose
  const [confirmDel, setConfirmDel] = useState(null); // id pendiente de confirmar
  const [busy, setBusy] = useState(false);
  const [customName, setCustomName] = useState("");
  const [pullError, setPullError] = useState(null); // {model} de la última descarga fallida
  const [pullProgress, setPullProgress] = useState(null); // {completed, total} en bytes
  const [refreshing, setRefreshing] = useState(false);
  const [collapsed, toggleCollapsed] = useCollapsed("models");

  // force=true salta la caché de sesión: se usa al refrescar a mano y tras una
  // mutación (instalar/borrar), donde la lista ya ha cambiado.
  const load = async (force = false) => {
    try {
      setModels(await getModels(force));
    } catch { /* ignore */ }
  };

  // Resincroniza una descarga ya en curso (al cargar o al refrescar a mano).
  const syncPull = async () => {
    try {
      const st = await getModelPullStatus();
      if (st.status === "pulling") {
        setPulling(st.model);
        setPullProgress(st.total ? { completed: st.completed, total: st.total } : null);
      }
    } catch { /* ignore */ }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await load(true);
    await syncPull();
    setRefreshing(false);
  };

  useEffect(() => {
    (async () => {
      await load();
      // Si al abrir el panel ya hay una descarga en curso (iniciada antes de
      // recargar la página o desde otra pestaña), retomar el indicador.
      await syncPull();
      setLoading(false);
    })();
  }, []);

  // Polling del estado de descarga
  useEffect(() => {
    if (!pulling) return;
    const iv = setInterval(async () => {
      try {
        const st = await getModelPullStatus();
        if (st.status === "pulling") {
          setPullProgress(st.total ? { completed: st.completed, total: st.total } : null);
        } else if (st.status === "done" || st.status === "error" || st.status === "idle") {
          clearInterval(iv);
          if (st.status === "error") setPullError({ model: st.model || pulling, reason: st.error });
          setPulling(null);
          setPullProgress(null);
          await load(true); // la descarga terminó: releer la lista real
        }
      } catch { /* esperar */ }
    }, 2000);
    return () => clearInterval(iv);
  }, [pulling]);

  const handleInstall = async (id) => {
    setBusy(true);
    setPullError(null);
    setPullProgress(null);
    try {
      await pullModel(id);
      setPulling(id);
    } catch (err) { setPullError({ model: id, reason: apiErrorReason(err) }); }
    finally { setBusy(false); }
  };

  const handleInstallCustom = async () => {
    const name = customName.trim();
    if (!name) return;
    setBusy(true);
    setPullError(null);
    setPullProgress(null);
    try {
      await pullModel(name);
      setPulling(name);
      setCustomName("");
    } catch (err) { setPullError({ model: name, reason: apiErrorReason(err) }); }
    finally { setBusy(false); }
  };

  const handleDelete = async (id) => {
    setBusy(true);
    try {
      await deleteModel(id);
      setConfirmDel(null);
      await load(true);
    } catch { /* ignore */ }
    finally { setBusy(false); }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
        <div className="flex items-center gap-2">
          <Loader2 size={18} className="text-brand animate-spin" />
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("modelsCard.title")}</h2>
        </div>
      </div>
    );
  }
  if (!models) return null;

  // Agrupar por categoría (vienen ya ordenados por tipo y potencia desde el
  // backend) para mostrar secciones compactas en vez de una única lista larga.
  const groups = [];
  for (const m of models) {
    const last = groups[groups.length - 1];
    if (last && last.category === m.category) last.items.push(m);
    else groups.push({ category: m.category, items: [m] });
  }

  // Porcentaje de la descarga en curso (null si aún no se conoce el total).
  const pct = pullProgress && pullProgress.total
    ? Math.round((pullProgress.completed / pullProgress.total) * 100)
    : null;

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      <CollapsibleHeader
        icon={HardDrive}
        title={t("modelsCard.title")}
        collapsed={collapsed}
        onToggle={toggleCollapsed}
        actions={
          <Button
            variant="ghost"
            size="sm"
            className="!p-1.5 hover:text-brand"
            onClick={handleRefresh}
            disabled={refreshing || busy}
            title={t("hardware.refresh")}
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          </Button>
        }
      />

      {!collapsed && (<>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 mt-1">{t("modelsCard.subtitle")}</p>

      <div className="space-y-4">
        {groups.map((g) => (
          <div key={g.category}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1.5">
              {t(CATEGORY_KEY[g.category] || "modelsCard.catOther")}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {g.items.map((m) => (
                <div
                  key={m.id}
                  className="px-2.5 py-1.5 rounded-lg border border-slate-100 dark:border-slate-700/60 bg-slate-50/60 dark:bg-slate-700/20"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 flex items-baseline gap-1.5">
                      {m.installed && <Check size={12} className="text-success shrink-0 self-center" />}
                      <span className="text-sm font-mono text-slate-700 dark:text-slate-200 truncate" title={m.id}>{m.id}</span>
                      {m.sizeBytes ? (
                        <span className="text-[11px] text-slate-400 dark:text-slate-500 shrink-0">
                          {m.installed ? "" : "~"}{formatSize(m.sizeBytes)}
                        </span>
                      ) : null}
                    </div>
                    <div className="flex-shrink-0">
                      {!m.installed ? (
                        pulling === m.id ? (
                          <span className="inline-flex items-center gap-1 p-1.5 text-[11px] tabular-nums text-slate-500" title={t("modelsCard.downloading")}>
                            <Loader2 size={15} className="animate-spin" />
                            {pct !== null ? `${pct}%` : ""}
                          </span>
                        ) : (
                          <button
                            onClick={() => handleInstall(m.id)}
                            disabled={busy || !!pulling}
                            title={t("modelsCard.install")}
                            aria-label={t("modelsCard.install")}
                            className="p-1.5 rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-50"
                          >
                            <Download size={15} />
                          </button>
                        )
                      ) : !m.deletable ? (
                        <span
                          className="inline-flex p-1.5 text-slate-400"
                          title={m.active ? t("modelsCard.inUse") : t("modelsCard.fallback")}
                        >
                          <Lock size={14} />
                        </span>
                      ) : confirmDel === m.id ? (
                        <span className="inline-flex items-center gap-0.5">
                          <button
                            onClick={() => handleDelete(m.id)}
                            disabled={busy}
                            title={t("modelsCard.confirmDelete")}
                            aria-label={t("modelsCard.confirmDelete")}
                            className="p-1.5 rounded-lg text-white bg-red-500 hover:bg-red-600 disabled:opacity-50"
                          >
                            <Check size={14} />
                          </button>
                          <button
                            onClick={() => setConfirmDel(null)}
                            title={t("common.cancel", "Cancelar")}
                            aria-label={t("common.cancel", "Cancelar")}
                            className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-200/60 dark:hover:bg-slate-600/40"
                          >
                            <X size={14} />
                          </button>
                        </span>
                      ) : (
                        <button
                          onClick={() => setConfirmDel(m.id)}
                          disabled={busy}
                          title={t("modelsCard.deleteHint", { size: formatSize(m.sizeBytes) })}
                          aria-label={t("modelsCard.delete")}
                          className="p-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </div>
                  {confirmDel === m.id && m.deleteNote && (
                    <p className="mt-1.5 text-[11px] text-warning">{m.deleteNote}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-700/60">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
          {t("modelsCard.installByName")}
        </p>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={customName}
            onChange={(e) => setCustomName(e.target.value)}
            placeholder={t("modelsCard.installByNamePlaceholder")}
            disabled={busy || !!pulling}
            className="flex-1 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
          />
          <button
            onClick={handleInstallCustom}
            disabled={busy || !!pulling || !customName.trim()}
            className="inline-flex items-center gap-1 text-xs px-3 py-2 rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-50"
          >
            <Download size={12} /> {t("modelsCard.install")}
          </button>
        </div>
        {pulling && (
          <div className="mt-2.5">
            <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
              <Loader2 size={14} className="animate-spin text-brand shrink-0" />
              <span className="font-mono truncate" title={pulling}>{shortModelName(pulling)}</span>
              <span className="ml-auto shrink-0 tabular-nums text-slate-500 dark:text-slate-400">
                {pct !== null
                  ? `${t("modelsCard.downloading")} ${pct}% (${formatSize(pullProgress.completed)} / ${formatSize(pullProgress.total)})`
                  : t("modelsCard.downloading")}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
              <div
                className={`h-full bg-brand rounded-full transition-[width] ${pct !== null ? "" : "animate-pulse w-1/3"}`}
                style={pct !== null ? { width: `${pct}%` } : undefined}
              />
            </div>
          </div>
        )}
        {pullError && (
          <div className="mt-1.5">
            <p className="text-[11px] text-danger" title={pullError.model}>
              {t("modelsCard.pullFailed", { model: shortModelName(pullError.model) })}
            </p>
            {pullError.reason && (
              <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono break-words mt-0.5">
                {pullError.reason}
              </p>
            )}
          </div>
        )}
        <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-1.5">{t("modelsCard.installByNameHint")}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
          <a href="https://ollama.com/search" target="_blank" rel="noopener noreferrer"
             className="text-[11px] text-brand hover:underline">{t("modelsCard.exploreOllama")}</a>
          <a href="https://huggingface.co/models?library=gguf&sort=trending" target="_blank" rel="noopener noreferrer"
             className="text-[11px] text-brand hover:underline">{t("modelsCard.exploreHfGguf")}</a>
          <a href="https://huggingface.co/models?search=faster-whisper" target="_blank" rel="noopener noreferrer"
             className="text-[11px] text-brand hover:underline">{t("modelsCard.exploreHfVoice")}</a>
        </div>
      </div>
      </>)}
    </div>
  );
}
