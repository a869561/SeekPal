import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, CheckCircle, AlertCircle, Sparkles, Mic, Film, Layers, RefreshCw, FileText, Download, ScanText, Eye, MessageSquare, HardDrive } from "lucide-react";
import { getSettings, saveSettings } from "../../api/settings.js";
import InfoHint from "../ui/InfoHint.jsx";
import Button from "../ui/Button.jsx";
import CollapsibleHeader from "../ui/CollapsibleHeader.jsx";
import useCollapsed from "../../hooks/useCollapsed.js";
import {
  restartApp, invalidateHardwareCache,
  getDoclingStatus, installDocling, getModels,
} from "../../api/system.js";

const OCR_QUALITY_OPTIONS = [
  { id: "mobile", sizeMB: 15,  note: "Rápido, texto impreso claro" },
  { id: "server", sizeMB: 140, note: "Preciso, fuentes estilizadas y juegos" },
];

// Todos los tamaños de Whisper conocidos (para el selector de descarga)
const WHISPER_SIZES = [
  { id: "tiny",     sizeMB: 39,   note: "Mas rapido, calidad baja" },
  { id: "base",     sizeMB: 74,   note: "Rapido, calidad moderada" },
  { id: "small",    sizeMB: 244,  note: "Buena calidad, algo mas lento" },
  { id: "medium",   sizeMB: 769,  note: "Mejor calidad, mas lento" },
  { id: "large-v3", sizeMB: 3090, note: "Maxima calidad, muy pesado" },
];

// Valores por defecto para campos que el servidor puede devolver como null.
// Deben coincidir con los ?? fallbacks del JSX para que el formulario no
// marque un campo como "cambiado" solo por hacer click en él.
const FIELD_DEFAULTS = {
  rerankerEnabled: true,
  whisperModel: "small",
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

  const [installed, setInstalled] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [collapsed, toggleCollapsed] = useCollapsed("rag");

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
      try {
        const ms = await getModels();
        setInstalled(ms);
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, []);

  // Polling del estado de instalacion de Docling (puede tardar varios minutos)
  useEffect(() => {
    if (doclingState !== "installing") return;
    const interval = setInterval(async () => {
      try {
        const ds = await getDoclingStatus(true); // estado cambiando: ir a red
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

  // Refresca la lista de modelos instalados (para que los recién descargados
  // aparezcan en los desplegables) y el estado de Docling, sin tocar el
  // formulario para no descartar cambios sin guardar.
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const ms = await getModels(true);
      setInstalled(ms);
    } catch { /* ignore */ }
    try {
      const ds = await getDoclingStatus(true);
      setDoclingInstalled(!!ds.installed);
    } catch { /* ignore */ }
    setRefreshing(false);
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

  const optionsFor = (category, current) => {
    const ids = installed.filter((m) => m.category === category && m.installed).map((m) => m.id);
    if (current && !ids.includes(current)) ids.unshift(current);
    return ids;
  };
  const llmOptions = optionsFor("llm", form.llmModel);
  const visionOptions = optionsFor("vision", form.visionModel);

  // Whisper: solo los tamaños instalados (manager=whisper, installed=true)
  // más el activo actual por seguridad. El id en el backend es "whisper:<size>".
  const installedWhisperModels = installed.filter((m) => m.manager === "whisper" && m.installed);
  const installedWhisperSizes = installedWhisperModels.map((m) => {
    // id puede ser "whisper:small" o directamente "small"
    const raw = m.id || "";
    return raw.startsWith("whisper:") ? raw.slice("whisper:".length) : raw;
  });
  const activeWhisperSize = form.whisperModel || "small";
  const whisperSelectOptions = installedWhisperSizes.includes(activeWhisperSize)
    ? installedWhisperSizes
    : [activeWhisperSize, ...installedWhisperSizes];

  const whisperMeta = (id) => WHISPER_SIZES.find((m) => m.id === id);

  const visionModelInfo = installed.find((m) => m.id === form.visionModel);
  const visionLacksCapability = !!visionModelInfo && visionModelInfo.category !== "vision";

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
        const fresh = await getSettings(true);
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
        await getSettings(true); // debe llegar a red para detectar el backend caído/vivo
        return;
      } catch {
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
  };

  const update = (key, value) => setForm({ ...form, [key]: value });

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      <CollapsibleHeader
        icon={Sparkles}
        title={t("ragSettings.title")}
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
      <div className="mt-5" />

      {/* Reranker */}
      <div className="mb-5 flex items-center justify-between gap-3">
        <OptionHeader icon={Layers} title={t("ragSettings.reranker")} hint={t("ragSettings.rerankerHint")} />
        <Toggle
          checked={form.rerankerEnabled ?? true}
          onChange={(v) => update("rerankerEnabled", v)}
          disabled={busy}
        />
      </div>

      {/* Modelo LLM de respuestas (conmutable: CPU vs GPU) */}
      <div className="mb-5">
        <OptionHeader icon={MessageSquare} title={t("ragSettings.llmModel")} hint={t("ragSettings.llmModelHint")} />
        <select
          value={form.llmModel || "llama3.2:3b"}
          disabled={busy}
          onChange={(e) => update("llmModel", e.target.value)}
          className="w-full mt-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {llmOptions.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
      </div>

      {/* Docling — PDFs estructurados (opt-in, ~2 GB) */}
      <div className="mb-5">
        <div className="flex items-center justify-between gap-3">
          <OptionHeader
            icon={FileText}
            title={t("ragSettings.useDocling", "PDFs estructurados (Docling)")}
            hint={t(
              "ragSettings.useDoclingHint",
              "Preserva tablas, multi-columna y OCR de PDFs escaneados. ~30x mas lento que PyMuPDF."
            )}
          />
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
      <div className="mb-5 flex items-center justify-between gap-3">
        <OptionHeader icon={Film} title={t("ragSettings.indexMultimedia")} hint={t("ragSettings.indexMultimediaHint")} />
        <Toggle
          checked={form.indexMultimedia ?? true}
          onChange={(v) => update("indexMultimedia", v)}
          disabled={busy}
        />
      </div>

      {/* Calidad OCR */}
      <div className="mb-5">
        <OptionHeader icon={ScanText} title={t("ragSettings.ocrQuality")} hint={t("ragSettings.ocrQualityHint")} />
        <select
          value={form.ocrQuality || "mobile"}
          disabled={busy || !(form.indexMultimedia ?? true)}
          onChange={(e) => update("ocrQuality", e.target.value)}
          className="w-full mt-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
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
        <OptionHeader icon={Mic} title={t("ragSettings.whisperModel")} hint={t("ragSettings.whisperModelHint")} />

        {/* Solo los tamaños instalados */}
        <select
          value={activeWhisperSize}
          disabled={busy || !(form.indexMultimedia ?? true)}
          onChange={(e) => update("whisperModel", e.target.value)}
          className="w-full mt-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {whisperSelectOptions.map((id) => {
            const m = whisperMeta(id);
            const label = m
              ? `${m.id} (${m.sizeMB >= 1000 ? `${(m.sizeMB / 1000).toFixed(1)} GB` : `${m.sizeMB} MB`}) — ${m.note}`
              : id;
            return (
              <option key={id} value={id}>{label}</option>
            );
          })}
        </select>
      </div>

      {/* Modelo de visión (captioning de imágenes) */}
      <div className="mb-5">
        <OptionHeader icon={Eye} title={t("ragSettings.visionModel")} hint={t("ragSettings.visionModelHint")} />
        <select
          value={form.visionModel || "qwen2.5vl:3b"}
          disabled={busy || !(form.indexMultimedia ?? true)}
          onChange={(e) => update("visionModel", e.target.value)}
          className="w-full mt-2 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {visionOptions.map((id) => (
            <option key={id} value={id}>{id}</option>
          ))}
        </select>
        {visionOptions.length === 0 && (
          <p className="text-[11px] text-slate-400 mt-1">{t("ragSettings.noInstalledModels")}</p>
        )}
        {visionLacksCapability && (
          <p className="text-[11px] text-warning mt-1">{t("ragSettings.visionNoVisionWarning")}</p>
        )}

        {/* Liberar el modelo anterior al cambiar (gestión de disco, opt-in) */}
        <div className="flex items-center justify-between gap-3 mt-3">
          <OptionHeader icon={HardDrive} title={t("ragSettings.autoFreeVision")} hint={t("ragSettings.autoFreeVisionHint")} />
          <Toggle
            checked={form.autoFreePreviousVisionModel ?? false}
            onChange={(v) => update("autoFreePreviousVisionModel", v)}
            disabled={busy}
          />
        </div>
      </div>

      {/* Frame interval + max frames (solo si multimedia ON) */}
      <div className={`grid grid-cols-2 gap-3 mb-5 ${!(form.indexMultimedia ?? true) ? "opacity-50" : ""}`}>
        <div>
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200 block mb-1">
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
          <label className="text-sm font-medium text-slate-700 dark:text-slate-200 block mb-1">
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
          <Button
            variant="primary"
            size="lg"
            className="w-full"
            onClick={handleApply}
          >
            {needsRestart ? t("ragSettings.applyRestart") : t("ragSettings.apply")}
          </Button>
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
      </>)}
    </div>
  );
}

// Cabecera unificada de cada ajuste: icono + título (mismo estilo para todas
// las opciones, sean conmutadores o desplegables) + "?" con la descripción.
function OptionHeader({ icon: Icon, title, hint }) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      {Icon && <Icon size={16} className="text-slate-400 shrink-0" />}
      <span className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">{title}</span>
      <InfoHint text={hint} />
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
