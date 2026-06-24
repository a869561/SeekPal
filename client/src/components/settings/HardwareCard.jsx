import { useState, useEffect, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import {
  Cpu, MemoryStick, Monitor, CheckCircle, AlertCircle,
  Loader2, RefreshCw, SlidersHorizontal,
} from "lucide-react";
import {
  getHardwareInfo, restartApp,
  invalidateHardwareCache, planPreview,
} from "../../api/system.js";
import { getSettings, saveSettings } from "../../api/settings.js";
import Button from "../ui/Button.jsx";
import InfoHint from "../ui/InfoHint.jsx";
import CollapsibleHeader from "../ui/CollapsibleHeader.jsx";
import useCollapsed from "../../hooks/useCollapsed.js";

// Icono de tarjeta gráfica (lucide no tiene uno específico)
const GpuIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01" />
    <path d="M8 14h8" />
  </svg>
);

// Componentes gestionados por el planificador (orden de display)
const DEVICE_COMPONENTS = ["embeddings", "reranker", "whisper", "ocr", "llm", "vision"];

// Devuelve siempre las 6 claves con orden canónico; lo ausente cuenta como "auto".
const normalizeOverrides = (o) => {
  const out = {};
  for (const c of DEVICE_COMPONENTS) out[c] = (o || {})[c] || "auto";
  return out;
};

// Compara overrides por valor efectivo (ignora claves ausentes / orden).
const overridesEqual = (a, b) =>
  DEVICE_COMPONENTS.every((c) => ((a || {})[c] || "auto") === ((b || {})[c] || "auto"));

const PLANNER_DEFAULTS = {
  processingPriority: "search",
  deviceOverrides: {
    embeddings: "auto", reranker: "auto", whisper: "auto",
    ocr: "auto", llm: "auto", vision: "auto",
  },
};

export default function HardwareCard() {
  const { t } = useTranslation();
  const [hw, setHw] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // ── Estado del planificador ─────────────────────────────────────────────
  const [plannerForm, setPlannerForm] = useState(PLANNER_DEFAULTS);
  const [plannerOriginal, setPlannerOriginal] = useState(PLANNER_DEFAULTS);
  const [plannerState, setPlannerState] = useState("idle"); // idle | saving | restarting | done | error | ingestPending
  const [preview, setPreview] = useState(null); // resultado del dry-run
  const [previewLoading, setPreviewLoading] = useState(false);
  const debounceRef = useRef(null);

  // ── Colapso ─────────────────────────────────────────────────────────────
  const [collapsed, toggleCollapsed] = useCollapsed("hardware");
  const [devicesCollapsed, toggleDevicesCollapsed] = useCollapsed("hardware-devices-advanced", true);

  const fetchHardware = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const data = await getHardwareInfo(force);
      setHw(data);
    } catch {
      // Errores de red: la card no muestra datos
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Carga inicial: hardware + settings para el planificador
  useEffect(() => {
    fetchHardware(false);
    (async () => {
      try {
        const data = await getSettings();
        const snap = {
          processingPriority: data.processingPriority ?? PLANNER_DEFAULTS.processingPriority,
          deviceOverrides: normalizeOverrides(data.deviceOverrides),
        };
        setPlannerOriginal(snap);
        setPlannerForm({ ...snap });
      } catch { /* ignore */ }
    })();
  }, [fetchHardware]);

  // ── Dry-run con debounce al cambiar preset u overrides ──────────────────
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setPreviewLoading(true);
      try {
        const result = await planPreview({
          processingPriority: plannerForm.processingPriority,
          deviceOverrides: plannerForm.deviceOverrides,
        });
        setPreview(result);
      } catch {
        setPreview(null);
      } finally {
        setPreviewLoading(false);
      }
    }, 500);
    return () => clearTimeout(debounceRef.current);
  }, [plannerForm.processingPriority, plannerForm.deviceOverrides]);

  // ── Aplicar cambios del planificador ─────────────────────────────────────
  const waitForPlannerRestart = async () => {
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

  const handlePlannerApply = async () => {
    if (preview && !preview.feasible) return; // bloqueado
    setPlannerState("saving");
    try {
      const patch = {};
      if (plannerForm.processingPriority !== plannerOriginal.processingPriority)
        patch.processingPriority = plannerForm.processingPriority;
      if (!overridesEqual(plannerForm.deviceOverrides, plannerOriginal.deviceOverrides))
        patch.deviceOverrides = plannerForm.deviceOverrides;

      if (Object.keys(patch).length === 0) {
        setPlannerState("idle");
        return;
      }

      await saveSettings(patch);
      setPlannerState("restarting");
      invalidateHardwareCache();
      try {
        await restartApp(false);
      } catch (err) {
        if (err?.response?.status === 409) {
          const newOriginal = { ...plannerOriginal, ...patch };
          setPlannerOriginal(newOriginal);
          setPlannerForm({ ...newOriginal });
          setPlannerState("ingestPending");
          setTimeout(() => setPlannerState("idle"), 6000);
          return;
        }
      }
      await waitForPlannerRestart();
      const fresh = await getSettings(true);
      const snap = {
        processingPriority: fresh.processingPriority ?? PLANNER_DEFAULTS.processingPriority,
        deviceOverrides: normalizeOverrides(fresh.deviceOverrides),
      };
      setPlannerOriginal(snap);
      setPlannerForm({ ...snap });
      setPlannerState("done");
      setTimeout(() => setPlannerState("idle"), 3000);
    } catch {
      setPlannerState("error");
    }
  };

  const updatePlanner = (key, value) =>
    setPlannerForm((f) => ({ ...f, [key]: value }));

  const updateDeviceOverride = (comp, value) =>
    setPlannerForm((f) => ({
      ...f,
      deviceOverrides: { ...f.deviceOverrides, [comp]: value },
    }));

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
        <div className="flex items-center gap-2">
          <Loader2 size={18} className="text-brand animate-spin" />
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("hardware.title")}</h2>
        </div>
      </div>
    );
  }

  if (!hw) return null;

  const hasGpu = hw.gpus && hw.gpus.length > 0;

  // Planificador: cambios y feasibilidad (comparación por valor efectivo)
  const plannerHasChanges =
    plannerForm.processingPriority !== plannerOriginal.processingPriority ||
    !overridesEqual(plannerForm.deviceOverrides, plannerOriginal.deviceOverrides);
  const plannerBusy = plannerState === "saving" || plannerState === "restarting";
  const busy = plannerBusy;

  const infeasible = preview && !preview.feasible;
  const plannerApplyDisabled = plannerBusy || infeasible || !plannerHasChanges;

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      {/* Cabecera plegable con botón refrescar */}
      <CollapsibleHeader
        icon={SlidersHorizontal}
        title={t("hardware.title")}
        collapsed={collapsed}
        onToggle={toggleCollapsed}
        actions={
          <Button
            variant="ghost"
            size="sm"
            className="!p-1.5 hover:text-brand"
            onClick={() => fetchHardware(true)}
            disabled={refreshing || busy}
            title={t("hardware.refresh")}
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
          </Button>
        }
      />

      {!collapsed && (<>
      <div className="mt-5" />

      {/* Lista de componentes detectados */}
      <div className="space-y-2 mb-5">
        <div className="flex items-start gap-3">
          <Cpu size={16} className="text-slate-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t("hardware.cpu")}</div>
            <div className="text-sm text-slate-700 dark:text-slate-200">{hw.cpu || t("hardware.unknown")}</div>
          </div>
        </div>

        <div className="flex items-start gap-3">
          <MemoryStick size={16} className="text-slate-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t("hardware.ram")}</div>
            <div className="text-sm text-slate-700 dark:text-slate-200">{hw.ram_gb} GB</div>
          </div>
        </div>

        {hw.gpus && hw.gpus.map((gpu, i) => (
          <div key={i} className="flex items-start gap-3">
            <GpuIcon className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
                {t("hardware.gpu")} {hw.gpus.length > 1 ? i + 1 : ""}
              </div>
              <div className="text-sm text-slate-700 dark:text-slate-200">{gpu}</div>
            </div>
          </div>
        ))}

        {!hasGpu && (
          <div className="flex items-start gap-3">
            <Monitor size={16} className="text-slate-400 mt-0.5 shrink-0" />
            <div className="text-sm text-slate-500 dark:text-slate-400">{t("hardware.noGpu")}</div>
          </div>
        )}
      </div>

      {/* ══ SECCIÓN: Rendimiento / Dispositivos (planificador) ══ */}
      <div className="border-t border-slate-100 dark:border-slate-700 pt-5 mb-5">
        <div className="flex items-center gap-2 mb-4">
          <SlidersHorizontal size={16} className="text-brand shrink-0" />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            {t("devicePlanner.sectionTitle")}
          </span>
        </div>

        {/* Selector "Modo de optimización" */}
        <div className="mb-4">
          <div className="flex items-center gap-1.5 mb-1.5">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              {t("devicePlanner.priorityLabel")}
            </label>
            <InfoHint text={t("devicePlanner.priorityHint")} />
          </div>
          <select
            value={plannerForm.processingPriority}
            disabled={plannerBusy}
            onChange={(e) => updatePlanner("processingPriority", e.target.value)}
            className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
          >
            <option value="search">{t("devicePlanner.prioritySearch")} — {t("devicePlanner.prioritySearchDesc")}</option>
            <option value="ingest">{t("devicePlanner.priorityIngest")} — {t("devicePlanner.priorityIngestDesc")}</option>
          </select>
        </div>

        {/* Guía VRAM del dry-run */}
        {preview && (
          <div className="mb-3 text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
            {previewLoading
              ? <Loader2 size={12} className="animate-spin text-brand" />
              : null
            }
            <span>
              {t("devicePlanner.vramUsage", {
                used: preview.gpu_used_mib,
                budget: preview.budget_mib,
              })}
            </span>
          </div>
        )}
        {previewLoading && !preview && (
          <div className="mb-3 text-xs text-brand flex items-center gap-1.5">
            <Loader2 size={12} className="animate-spin" />
            {t("devicePlanner.calculating")}
          </div>
        )}

        {/* Banner de infeasibilidad */}
        {infeasible && (
          <div className="mb-4 rounded-xl p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 flex items-start gap-2">
            <AlertCircle size={15} className="text-danger shrink-0 mt-0.5" />
            <div className="text-sm text-danger">
              <p className="font-medium">
                {t("devicePlanner.infeasibleBanner", { vram: preview.vram_total_mib })}
              </p>
              {preview.overflow && preview.overflow.length > 0 && (
                <p className="mt-0.5 text-xs">
                  {t("devicePlanner.overflowComponents")}: {preview.overflow.join(", ")}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Sección avanzada plegable: overrides por componente */}
        <div className="mb-4">
          <CollapsibleHeader
            icon={null}
            title={t("devicePlanner.advancedTitle")}
            collapsed={devicesCollapsed}
            onToggle={toggleDevicesCollapsed}
          />
          {!devicesCollapsed && (
            <div className="mt-2 space-y-1 pl-2">
              {DEVICE_COMPONENTS.map((comp) => {
                const currentVal = (plannerForm.deviceOverrides || {})[comp] || "auto";
                const resolvedDevice = preview?.devices?.[comp];
                return (
                  <div key={comp} className="flex items-center gap-2">
                    <div className="flex-1 min-w-0 flex items-center gap-1 flex-wrap">
                      <span className="text-sm text-slate-700 dark:text-slate-200">{t(`devicePlanner.${comp}`)}</span>
                      <InfoHint text={t(`devicePlanner.${comp}Hint`)} />
                      {resolvedDevice && (
                        <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400">
                          {resolvedDevice === "cuda" ? "GPU" : "CPU"}
                        </span>
                      )}
                    </div>
                    <select
                      value={currentVal}
                      disabled={plannerBusy}
                      onChange={(e) => updateDeviceOverride(comp, e.target.value)}
                      className="w-24 shrink-0 px-2 py-1.5 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
                    >
                      <option value="auto">{t("devicePlanner.deviceAuto")}</option>
                      <option value="gpu">{t("devicePlanner.deviceGpu")}</option>
                      <option value="cpu">{t("devicePlanner.deviceCpu")}</option>
                    </select>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Aviso de reinicio + botón Aplicar del planificador */}
        {plannerState === "idle" && plannerHasChanges && (
          <>
            <div className="text-xs text-warning mb-2 flex items-center gap-1.5">
              <AlertCircle size={12} /> {t("ragSettings.restartRequired")}
            </div>
            <Button
              variant="primary"
              size="lg"
              className="w-full"
              onClick={handlePlannerApply}
              disabled={plannerApplyDisabled}
            >
              {t("ragSettings.applyRestart")}
            </Button>
          </>
        )}

        {plannerState === "saving" && (
          <div className="flex items-center gap-2 text-sm text-brand">
            <Loader2 size={15} className="animate-spin" />
            {t("ragSettings.saving")}
          </div>
        )}
        {plannerState === "restarting" && (
          <div className="flex items-center gap-2 text-sm text-brand">
            <Loader2 size={15} className="animate-spin" />
            {t("ragSettings.restarting")}
          </div>
        )}
        {plannerState === "done" && (
          <div className="flex items-center gap-2 text-sm text-success">
            <CheckCircle size={15} /> {t("ragSettings.done")}
          </div>
        )}
        {plannerState === "ingestPending" && (
          <div className="flex items-start gap-2 text-sm text-warning">
            <AlertCircle size={15} className="mt-0.5 shrink-0" /> {t("ragSettings.ingestPending")}
          </div>
        )}
        {plannerState === "error" && (
          <div className="flex items-center gap-2 text-sm text-danger">
            <AlertCircle size={15} /> {t("ragSettings.error")}
          </div>
        )}
      </div>
      </>)}
    </div>
  );
}
