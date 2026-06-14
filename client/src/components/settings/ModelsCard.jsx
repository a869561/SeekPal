import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, HardDrive, Download, Trash2, Check, Lock } from "lucide-react";
import { getModels, pullModel, getModelPullStatus, deleteModel } from "../../api/system.js";

function formatSize(bytes) {
  if (!bytes) return "";
  const gb = bytes / 1e9;
  if (gb >= 1) return `${gb.toFixed(1)} GB`;
  return `${Math.round(bytes / 1e6)} MB`;
}

const CATEGORY_KEY = {
  vision: "modelsCard.catVision",
  llm: "modelsCard.catLlm",
  otro: "modelsCard.catOther",
};

export default function ModelsCard() {
  const { t } = useTranslation();
  const [models, setModels] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pulling, setPulling] = useState(null); // id del modelo descargándose
  const [confirmDel, setConfirmDel] = useState(null); // id pendiente de confirmar
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setModels(await getModels());
    } catch { /* ignore */ }
  };

  useEffect(() => {
    (async () => { await load(); setLoading(false); })();
  }, []);

  // Polling del estado de descarga
  useEffect(() => {
    if (!pulling) return;
    const iv = setInterval(async () => {
      try {
        const st = await getModelPullStatus();
        if (st.status === "done" || st.status === "error" || st.status === "idle") {
          clearInterval(iv);
          setPulling(null);
          await load();
        }
      } catch { /* esperar */ }
    }, 2000);
    return () => clearInterval(iv);
  }, [pulling]);

  const handleInstall = async (id) => {
    setBusy(true);
    try {
      await pullModel(id);
      setPulling(id);
    } catch { /* ignore */ }
    finally { setBusy(false); }
  };

  const handleDelete = async (id) => {
    setBusy(true);
    try {
      await deleteModel(id);
      setConfirmDel(null);
      await load();
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

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      <div className="flex items-center gap-2 mb-1">
        <HardDrive size={18} className="text-brand" />
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("modelsCard.title")}</h2>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">{t("modelsCard.subtitle")}</p>

      <div className="space-y-2">
        {models.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-100 dark:border-slate-700/60 bg-slate-50/60 dark:bg-slate-700/20"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{m.label}</span>
                {m.installed ? (
                  <span className="inline-flex items-center gap-0.5 text-[10px] text-success">
                    <Check size={11} /> {t("modelsCard.installed")}
                  </span>
                ) : (
                  <span className="text-[10px] text-slate-400">{t("modelsCard.notInstalled")}</span>
                )}
                {m.active && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand/10 text-brand">{t("modelsCard.inUse")}</span>
                )}
              </div>
              <div className="text-[11px] text-slate-400 dark:text-slate-500">
                {t(CATEGORY_KEY[m.category] || "modelsCard.catOther")}
                {m.installed && m.sizeBytes ? ` · ${formatSize(m.sizeBytes)}` : ""}
              </div>
            </div>

            <div className="flex-shrink-0">
              {!m.installed ? (
                pulling === m.id ? (
                  <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                    <Loader2 size={13} className="animate-spin" /> {t("modelsCard.downloading")}
                  </span>
                ) : (
                  <button
                    onClick={() => handleInstall(m.id)}
                    disabled={busy || !!pulling}
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-brand text-white hover:bg-brand/90 disabled:opacity-50"
                  >
                    <Download size={12} /> {t("modelsCard.install")}
                  </button>
                )
              ) : !m.deletable ? (
                <span className="inline-flex items-center gap-1 text-[11px] text-slate-400" title={t("modelsCard.protectedHint")}>
                  <Lock size={12} /> {m.active ? t("modelsCard.inUse") : t("modelsCard.fallback")}
                </span>
              ) : confirmDel === m.id ? (
                <span className="inline-flex items-center gap-1">
                  <button
                    onClick={() => handleDelete(m.id)}
                    disabled={busy}
                    className="text-xs px-2 py-1.5 rounded-lg bg-danger text-white hover:bg-danger/90 disabled:opacity-50"
                  >
                    {t("modelsCard.confirmDelete")}
                  </button>
                  <button
                    onClick={() => setConfirmDel(null)}
                    className="text-xs px-2 py-1.5 rounded-lg text-slate-500 hover:text-slate-700"
                  >
                    {t("common.cancel", "Cancelar")}
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => setConfirmDel(m.id)}
                  disabled={busy}
                  className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg text-danger hover:bg-danger/10 disabled:opacity-50"
                  title={t("modelsCard.deleteHint", { size: formatSize(m.sizeBytes) })}
                >
                  <Trash2 size={12} /> {t("modelsCard.delete")}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
