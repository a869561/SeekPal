import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, CheckCircle, AlertCircle, Sparkles, Mic, Film, Layers, RefreshCw, FileText, Download, ScanText, Eye, MessageSquare } from "lucide-react";
import { getSettings, saveSettings } from "../../api/settings.js";
import {
  restartApp, invalidateHardwareCache,
  getDoclingStatus, installDocling,
} from "../../api/system.js";

const OCR_QUALITY_OPTIONS = [
  { id: "mobile", sizeMB: 15,  note: "Rápido, texto impreso claro" },
  { id: "server", sizeMB: 140, note: "Preciso, fuentes estilizadas y juegos" },
];

const WHISPER_MODELS = [
  { id: "tiny",   sizeMB: 39,   note: "Mas rapido, calidad baja" },
  { id: "base",   sizeMB: 74,   note: "Rapido, calidad moderada" },
  { id: "small",  sizeMB: 244,  note: "Buena calidad, algo mas lento" },
  { id: "medium", sizeMB: 769,  note: "Mejor calidad, mas lento" },
];

const VISION_MODELS = [
  { id: "qwen2.5vl:3b", labelKey: "ragSettings.visionModelQwen" },
  { id: "moondream",    labelKey: "ragSettings.visionModelMoondream" },
];

// LLM de respuestas. llama3.2:3b corre en CPU (PC sin gráfica); qwen3:4b da
// mejor calidad pero requiere GPU/RAM (en 4 GB se satura y agota el timeout).
const LLM_MODELS = [
  { id: "llama3.2:3b", labelKey: "ragSettings.llmModelLlama" },
  { id: "qwen3:4b",    labelKey: "ragSettings.llmModelQwen" },
];

// Valores por defecto para campos que el servidor puede devolver como null.
// Deben coincidir con los ?? fallbacks del JSX para que el formulario no
// marque un campo como "cambiado" solo por hacer click en él.
const FIELD_DEFAULTS = {
  rerankerEnabled: true,
  whisperModel: "base",
  useDocling: false,
  indexMultimedia: true,
  videoFrameInterval: 30,
  videoMaxFrames: 20,
  ocrQuality: "mobile",
  visionModel: "qwen2.5vl:3b",
  autoFreePreviousVisionModel: false,
  llmModel: "llama3.2:3b",
};

// Campos que requieren reiniciar el backend para entrar en efecto
const RESTART_FIELDS = new Set([
  "rerankerEnabled", "whisperModel", "useDocling", "indexMultimedia",
  "videoFrameInterval", "videoMaxFrames", "ocrQuality", "visionModel", "llmModel",
]);

export default function RagSettingsCard() {
  const { t } = useTranslation();
  const [original, setOriginal] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [state, setState] = useState("idle"); // idle | saving | restarting | done | error

  // Estado de la instalacion de Docling (separado del flujo de guardado RAG)
  const [doclingInstalled, setDoclingInstalled] = useState(false);
  const [doclingState, setDoclingState] = useState("idle"); // idle | installing | done | error

  useEffect(() => {
    (async () => {
      try {
        // getSettings() ya devuelve r.data.data directamente (el objeto de ajustes).
        // Aplicar defaults para campos que el servidor puede devolver como null,
        // evitando que interactuar con un campo lo marque como "cambiado".
        const data = await getSettings();
        const snapshot = { ...FIELD_DEFAULTS, ...data };
        setOriginal(snapshot);
        setForm({ ...snapshot });
      } catch { /* ignore */ }
      try {
        const ds = await getDoclingStatus();
        setDoclingInstalled(!!ds.installed);
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, []);

  // Polling del estado de instalacion de Docling (puede tardar varios minutos)
  useEffect(() => {
    if (doclingState !== "installing") return;
    const interval = setInterval(async () => {
      try {
        const ds = await getDoclingStatus();
        if (ds.status === "done" || ds.installed) {
          setDoclingInstalled(true);
          setDoclingState("done");
          clearInterval(interval);
          setTimeout(() => setDoclingState("idle"), 3000);
        } else if (ds.status === "error") {
          setDoclingState("error");
          clearInterval(interval);
        }
      } catch { /* esperar */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [doclingState]);

  const handleInstallDocling = async () => {
    setDoclingState("installing");
    try {
      await installDocling();
    } catch {
      setDoclingState("error");
    }
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
        <div className="flex items-center gap-2">
          <Loader2 size={18} className="text-brand animate-spin" />
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
        try {
          await restartApp(false);
        } catch (err) {
          // 409 = hay una ingesta en curso. Los ajustes quedan guardados en
          // Mongo y se aplicarán al reiniciar; NO forzamos el reinicio para no
          // cortar la ingesta. Avisamos al usuario en vez de fingir "aplicado".
          if (err?.response?.status === 409) {
            setOriginal({ ...original, ...patch });
            setForm({ ...original, ...patch });
            setState("ingestPending");
            setTimeout(() => setState("idle"), 6000);
            return;
          }
          // Otros errores: caemos al flujo normal (waitForRestart reintenta).
        }
        await waitForRestart();
        setState("done");
        const fresh = await getSettings();
        const snapshot = { ...FIELD_DEFAULTS, ...fresh };
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
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      <div className="flex items-center gap-2 mb-5">
        <Sparkles size={18} className="text-brand" />
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

      {/* Modelo LLM de respuestas (conmutable: CPU vs GPU) */}
      <div className="mb-5">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">
          <MessageSquare size={13} /> {t("ragSettings.llmModel")}
        </label>
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-2 ml-5">
          {t("ragSettings.llmModelHint")}
        </p>
        <select
          value={form.llmModel || "llama3.2:3b"}
          disabled={busy}
          onChange={(e) => update("llmModel", e.target.value)}
          className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {LLM_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {t(m.labelKey)}
            </option>
          ))}
        </select>
      </div>

      {/* Docling — PDFs estructurados (opt-in, ~2 GB) */}
      <div className="mb-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <FileText size={16} className="text-slate-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {t("ragSettings.useDocling", "PDFs estructurados (Docling)")}
              </div>
              <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                {t(
                  "ragSettings.useDoclingHint",
                  "Preserva tablas, multi-columna y OCR de PDFs escaneados. ~30x mas lento que PyMuPDF."
                )}
              </div>
            </div>
          </div>
          <Toggle
            checked={form.useDocling ?? false}
            onChange={(v) => update("useDocling", v)}
            disabled={busy || !doclingInstalled}
          />
        </div>

        {!doclingInstalled && doclingState === "idle" && (
          <div className="mt-2 ml-6 p-3 rounded-xl bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-600">
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-2">
              {t(
                "ragSettings.doclingNotInstalled",
                "Requiere instalar Docling (~2 GB: torch + transformers + modelos)."
              )}
            </p>
            <button
              onClick={handleInstallDocling}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand hover:brightness-110 active:scale-[0.97] text-white text-xs font-medium transition"
            >
              <Download size={12} />
              {t("ragSettings.installDocling", "Instalar Docling")}
            </button>
          </div>
        )}

        {doclingState === "installing" && (
          <div className="mt-2 ml-6 flex items-center gap-2 text-xs text-brand">
            <Loader2 size={12} className="animate-spin" />
            {t("ragSettings.installingDocling", "Descargando Docling (puede tardar 5-10 min)...")}
          </div>
        )}
        {doclingState === "done" && (
          <div className="mt-2 ml-6 flex items-center gap-2 text-xs text-success">
            <CheckCircle size={12} />
            {t("ragSettings.doclingInstalled", "Docling instalado. Activa el interruptor para usarlo.")}
          </div>
        )}
        {doclingState === "error" && (
          <div className="mt-2 ml-6 flex items-center gap-2 text-xs text-danger">
            <AlertCircle size={12} />
            {t("ragSettings.doclingError", "Error instalando Docling. Mira los logs del backend.")}
          </div>
        )}
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

      {/* Calidad OCR */}
      <div className="mb-5">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">
          <ScanText size={13} /> {t("ragSettings.ocrQuality")}
        </label>
        <p className="text-xs text-slate-400 dark:text-slate-500 mb-2 ml-5">
          {t("ragSettings.ocrQualityHint")}
        </p>
        <select
          value={form.ocrQuality || "mobile"}
          disabled={busy || !(form.indexMultimedia ?? true)}
          onChange={(e) => update("ocrQuality", e.target.value)}
          className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {OCR_QUALITY_OPTIONS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id} ({m.sizeMB} MB) — {m.note}
            </option>
          ))}
        </select>
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
          className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {WHISPER_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.id} ({m.sizeMB} MB) — {m.note}
            </option>
          ))}
        </select>
      </div>

      {/* Modelo de visión (captioning de imágenes) */}
      <div className="mb-5">
        <label className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2">
          <Eye size={13} /> {t("ragSettings.visionModel")}
        </label>
        <select
          value={form.visionModel || "qwen2.5vl:3b"}
          disabled={busy || !(form.indexMultimedia ?? true)}
          onChange={(e) => update("visionModel", e.target.value)}
          className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {VISION_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {t(m.labelKey)}
            </option>
          ))}
        </select>

        {/* Liberar el modelo anterior al cambiar (gestión de disco, opt-in) */}
        <label className="flex items-start gap-2 mt-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.autoFreePreviousVisionModel ?? false}
            disabled={busy}
            onChange={(e) => update("autoFreePreviousVisionModel", e.target.checked)}
            className="mt-0.5 accent-brand"
          />
          <span className="text-xs text-slate-600 dark:text-slate-300">
            {t("ragSettings.autoFreeVision")}
            <span className="block text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
              {t("ragSettings.autoFreeVisionHint")}
            </span>
          </span>
        </label>
      </div>

      {/* Frame interval + max frames (solo si multimedia ON) */}
      <div className={`grid grid-cols-2 gap-3 mb-5 ${!(form.indexMultimedia ?? true) ? "opacity-50" : ""}`}>
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-1">
            {t("ragSettings.frameInterval")}
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number" min={1} max={60} step={1}
              value={form.videoFrameInterval ?? 30}
              disabled={busy || !(form.indexMultimedia ?? true)}
              onChange={(e) => {
                if (e.target.value === "") { update("videoFrameInterval", ""); return; }
                const v = parseInt(e.target.value);
                if (!isNaN(v)) update("videoFrameInterval", Math.min(60, v));
              }}
              onBlur={(e) => {
                const v = parseInt(e.target.value);
                update("videoFrameInterval", isNaN(v) ? 30 : Math.max(1, Math.min(60, v)));
              }}
              className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
            />
            <span className="text-xs text-slate-400">s</span>
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-1">
            {t("ragSettings.maxFrames")}
          </label>
          <input
            type="number" min={1} max={60}
            value={form.videoMaxFrames ?? 20}
            disabled={busy || !(form.indexMultimedia ?? true)}
            onChange={(e) => {
              if (e.target.value === "") { update("videoMaxFrames", ""); return; }
              const v = parseInt(e.target.value);
              if (!isNaN(v)) update("videoMaxFrames", Math.min(60, v));
            }}
            onBlur={(e) => {
              const v = parseInt(e.target.value);
              update("videoMaxFrames", isNaN(v) ? 20 : Math.max(1, Math.min(60, v)));
            }}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
          />
        </div>
      </div>

      {/* Aviso de reinicio + boton */}
      {state === "idle" && hasChanges && (
        <>
          {needsRestart && (
            <div className="text-xs text-warning mb-2 flex items-center gap-1.5">
              <AlertCircle size={12} /> {t("ragSettings.restartRequired")}
            </div>
          )}
          <button
            onClick={handleApply}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-brand hover:brightness-110 active:scale-[0.98] text-white text-sm font-medium transition"
          >
            <RefreshCw size={15} />
            {needsRestart ? t("ragSettings.applyRestart") : t("ragSettings.apply")}
          </button>
        </>
      )}

      {state === "saving" && (
        <div className="flex items-center gap-2 text-sm text-brand">
          <Loader2 size={15} className="animate-spin" />
          {t("ragSettings.saving")}
        </div>
      )}
      {state === "restarting" && (
        <div className="flex items-center gap-2 text-sm text-brand">
          <Loader2 size={15} className="animate-spin" />
          {t("ragSettings.restarting")}
        </div>
      )}
      {state === "done" && (
        <div className="flex items-center gap-2 text-sm text-success">
          <CheckCircle size={15} /> {t("ragSettings.done")}
        </div>
      )}
      {state === "ingestPending" && (
        <div className="flex items-start gap-2 text-sm text-warning">
          <AlertCircle size={15} className="mt-0.5 shrink-0" /> {t("ragSettings.ingestPending")}
        </div>
      )}
      {state === "error" && (
        <div className="flex items-center gap-2 text-sm text-danger">
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
        checked ? "bg-brand" : "bg-slate-300 dark:bg-slate-600"
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
