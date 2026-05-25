import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, CheckCircle, AlertCircle, Sparkles, Mic, Film, Layers, RefreshCw } from "lucide-react";
import { getSettings, saveSettings } from "../../api/settings.js";
import { restartApp, invalidateHardwareCache } from "../../api/system.js";

const WHISPER_MODELS = [
  { id: "tiny",   sizeMB: 39,   note: "Mas rapido, calidad baja" },
  { id: "base",   sizeMB: 74,   note: "Rapido, calidad moderada" },
  { id: "small",  sizeMB: 244,  note: "Recomendado (informe v3)" },
  { id: "medium", sizeMB: 769,  note: "Mejor calidad, mas lento" },
];

// Campos que requieren reiniciar el backend para entrar en efecto
const RESTART_FIELDS = new Set([
  "rerankerEnabled", "whisperModel", "indexMultimedia",
  "videoFrameInterval", "videoMaxFrames",
]);

export default function RagSettingsCard() {
  const { t } = useTranslation();
  const [original, setOriginal] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [state, setState] = useState("idle"); // idle | saving | restarting | done | error

  useEffect(() => {
    (async () => {
      try {
        const data = await getSettings();
        const snapshot = data.data || data;
        setOriginal(snapshot);
        setForm({ ...snapshot });
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <Loader2 size={18} className="text-indigo-500 animate-spin" />
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("ragSettings.title")}</h2>
        </div>
      </div>
    );
  }
  if (!form || !original) return null;

  const changedFields = Object.keys(form).filter((k) => form[k] !== original[k]);
  const hasChanges = changedFields.length > 0;
  const needsRestart = changedFields.some((k) => RESTART_FIELDS.has(k));
  const busy = state === "saving" || state === "restarting";

  const handleApply = async () => {
    setState("saving");
    try {
      const patch = Object.fromEntries(changedFields.map((k) => [k, form[k]]));
      await saveSettings(patch);
      if (needsRestart) {
        setState("restarting");
        invalidateHardwareCache();
        try { await restartApp(false); } catch { /* ignore */ }
        await waitForRestart();
        setState("done");
        const fresh = await getSettings();
        const snapshot = fresh.data || fresh;
        setOriginal(snapshot);
        setForm({ ...snapshot });
        setTimeout(() => setState("idle"), 3000);
      } else {
        setOriginal({ ...original, ...patch });
        setState("done");
        setTimeout(() => setState("idle"), 2000);
      }
    } catch {
      setState("error");
    }
  };

  const waitForRestart = async () => {
    await new Promise((r) => setTimeout(r, 2000));
    for (let i = 0; i < 60; i++) {
      try {
        await getSettings();
        return;
      } catch {
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
  };

  const update = (key, value) => setForm({ ...form, [key]: value });

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-5">
        <Sparkles size={18} className="text-indigo-500" />
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("ragSettings.title")}</h2>
      </div>

      {/* Reranker */}
      <div className="mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <Layers size={16} className="text-slate-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-200">{t("ragSettings.reranker")}</div>
              <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{t("ragSettings.rerankerHint")}</div>
            </div>
          </div>
          <Toggle
            checked={form.rerankerEnabled ?? true}
            onChange={(v) => update("rerankerEnabled", v)}
            disabled={busy}
          />
        </div>
      </div>

      {/* Multimedia master switch */}
      <div className="mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <Film size={16} className="text-slate-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-200">{t("ragSettings.indexMultimedia")}</div>
              <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{t("ragSettings.indexMultimediaHint")}</div>
            </div>
          </div>
          <Toggle
            checked={form.indexMultimedia ?? true}
            onChange={(v) => update("indexMultimedia", v)}
            disabled={busy}
          />
        </div>
      </div>

      {/* Modelo Whisper */}
      <div className="mb-5">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          <Mic size={13} /> {t("ragSettings.whisperModel")}
        </label>
        <select
          value={form.whisperModel || "small"}
          disabled={busy || !(form.indexMultimedia ?? true)}
          onChange={(e) => update("whisperModel", e.target.value)}
          className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50"
        >
          {WHISPER_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id} ({m.sizeMB} MB) — {m.note}
            </option>
          ))}
        </select>
      </div>

      {/* Frame interval + max frames (solo si multimedia ON) */}
      <div className={`grid grid-cols-2 gap-3 mb-5 ${!(form.indexMultimedia ?? true) ? "opacity-50" : ""}`}>
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-1">
            {t("ragSettings.frameInterval")}
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number" min={5} max={300} step={5}
              value={form.videoFrameInterval ?? 30}
              disabled={busy || !(form.indexMultimedia ?? true)}
              onChange={(e) => update("videoFrameInterval", parseInt(e.target.value) || 30)}
              className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50"
            />
            <span className="text-xs text-slate-400">s</span>
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-1">
            {t("ragSettings.maxFrames")}
          </label>
          <input
            type="number" min={1} max={100}
            value={form.videoMaxFrames ?? 20}
            disabled={busy || !(form.indexMultimedia ?? true)}
            onChange={(e) => update("videoMaxFrames", parseInt(e.target.value) || 20)}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-50"
          />
        </div>
      </div>

      {/* Aviso de reinicio + boton */}
      {state === "idle" && hasChanges && (
        <>
          {needsRestart && (
            <div className="text-xs text-amber-600 dark:text-amber-400 mb-2 flex items-center gap-1.5">
              <AlertCircle size={12} /> {t("ragSettings.restartRequired")}
            </div>
          )}
          <button
            onClick={handleApply}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium transition"
          >
            <RefreshCw size={15} />
            {needsRestart ? t("ragSettings.applyRestart") : t("ragSettings.apply")}
          </button>
        </>
      )}

      {state === "saving" && (
        <div className="flex items-center gap-2 text-sm text-indigo-600 dark:text-indigo-400">
          <Loader2 size={15} className="animate-spin" />
          {t("ragSettings.saving")}
        </div>
      )}
      {state === "restarting" && (
        <div className="flex items-center gap-2 text-sm text-indigo-600 dark:text-indigo-400">
          <Loader2 size={15} className="animate-spin" />
          {t("ragSettings.restarting")}
        </div>
      )}
      {state === "done" && (
        <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
          <CheckCircle size={15} /> {t("ragSettings.done")}
        </div>
      )}
      {state === "error" && (
        <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
          <AlertCircle size={15} /> {t("ragSettings.error")}
        </div>
      )}
    </div>
  );
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
        checked ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-6" : "translate-x-1"
        }`}
      />
    </button>
  );
}
