import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, MemoryStick, Monitor, CheckCircle, AlertCircle, Loader2, RefreshCw, Zap } from "lucide-react";
import {
  getHardwareInfo, getInstallStatus, setProvider, restartApp, invalidateHardwareCache,
} from "../../api/system.js";
import Button from "../ui/Button.jsx";
import StatusDot from "../ui/StatusDot.jsx";

// Icono de tarjeta gráfica (lucide no tiene uno específico)
const GpuIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01" />
    <path d="M8 14h8" />
  </svg>
);

export default function HardwareCard() {
  const { t } = useTranslation();
  const [hw, setHw] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedPref, setSelectedPref] = useState("auto");
  const [installState, setInstallState] = useState("idle"); // idle | installing | restarting | done | error
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  const [pendingTarget, setPendingTarget] = useState(null);

  const fetchHardware = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    try {
      const data = await getHardwareInfo(force);
      setHw(data);
      setSelectedPref(data.preference || "auto");
    } catch {
      // Errores de red: la card no muestra datos
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchHardware(false); }, [fetchHardware]);

  // Polling del estado de instalación cuando hay un cambio en curso
  useEffect(() => {
    if (installState !== "installing") return;
    const interval = setInterval(async () => {
      try {
        const status = await getInstallStatus();
        if (status.status === "done") {
          setInstallState("restarting");
          clearInterval(interval);
          waitForRestart();
        } else if (status.status === "error") {
          setInstallState("error");
          clearInterval(interval);
        }
      } catch { /* esperar */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [installState]);

  // Espera a que el backend vuelva tras reinicio (exit 99 + relaunch de start.bat)
  const waitForRestart = async () => {
    await new Promise((r) => setTimeout(r, 2000));
    for (let i = 0; i < 60; i++) {
      try {
        invalidateHardwareCache();
        await getHardwareInfo(true);
        setInstallState("done");
        await fetchHardware(true);
        setTimeout(() => setInstallState("idle"), 3000);
        return;
      } catch {
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    setInstallState("error");
  };

  const applyPreference = async (target, force = false) => {
    setPendingTarget(target);
    setInstallState("installing");
    try {
      await setProvider(target);
    } catch (err) {
      if (err.response?.status === 409 && !force) {
        // Posible ingesta activa: mostrar confirmación
        setShowRestartConfirm(true);
        setInstallState("idle");
      } else {
        setInstallState("error");
      }
    }
  };

  const handleApply = () => applyPreference(selectedPref);

  const handleRestart = async (force = false) => {
    setShowRestartConfirm(false);
    setInstallState("restarting");
    try {
      await restartApp(force);
      waitForRestart();
    } catch (err) {
      if (!force && err.response?.status === 409) {
        setShowRestartConfirm(true);
        setInstallState("idle");
      } else {
        setInstallState("error");
      }
    }
  };

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

  const isGpuActive = hw.active_provider !== "CPUExecutionProvider";
  const hasGpu = hw.gpus && hw.gpus.length > 0;
  const currentPref = hw.preference || "auto";
  const hasChanges = selectedPref !== currentPref;
  const busy = installState === "installing" || installState === "restarting";

  // Lista para el selector: Auto + cada provider de la API
  const providers = hw.available_providers || [];
  const selectorOptions = [
    { id: "auto", label: t("hardware.autoOption"), available: true, reason: null },
    ...providers,
  ];

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-card">
      {/* Cabecera con botón refrescar */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Zap size={18} className="text-brand" />
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("hardware.title")}</h2>
        </div>
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
      </div>

      {/* Lista de componentes */}
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

      {/* Estado actual — marco neutro; el estado lo indica un punto, no un marco de color */}
      <div className="rounded-xl p-3 mb-4 flex items-center gap-3 bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-600">
        <StatusDot tone={isGpuActive ? "success" : hasGpu ? "warning" : "neutral"} />
        <div>
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t("hardware.aiProcessing")}</div>
          <div className="text-sm font-medium text-slate-700 dark:text-slate-200">
            {isGpuActive
              ? `${t("hardware.gpu")} ${hw.active_gpu_index != null ? hw.active_gpu_index + 1 : ""} — ${hw.active_label}`
              : hasGpu
                ? t("hardware.cpuFallback")
                : t("hardware.cpuOnly")
            }
          </div>
        </div>
      </div>

      {/* Selector de provider */}
      <div className="mb-3">
        <label className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide block mb-2">
          {t("hardware.selectEngine")}
        </label>
        <select
          value={selectedPref}
          disabled={busy}
          onChange={(e) => setSelectedPref(e.target.value)}
          className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-700 text-sm text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand/50 disabled:opacity-50"
        >
          {selectorOptions.map((opt) => (
            <option key={opt.id} value={opt.id} disabled={!opt.available}>
              {opt.label}{!opt.available && opt.reason ? ` — ${opt.reason}` : ""}
            </option>
          ))}
        </select>
        {selectedPref === "auto" && (
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1.5">{t("hardware.autoHint")}</p>
        )}
      </div>

      {/* Botón Aplicar */}
      {installState === "idle" && hasChanges && (
        <Button variant="primary" size="lg" className="w-full" onClick={handleApply}>
          <Zap size={15} />
          {t("hardware.applyButton")}
        </Button>
      )}

      {installState === "installing" && (
        <div className="flex items-center gap-2 text-sm text-brand">
          <Loader2 size={15} className="animate-spin" />
          {pendingTarget === "auto" ? t("hardware.applying") : t("hardware.downloading")}
        </div>
      )}

      {installState === "restarting" && (
        <div className="flex items-center gap-2 text-sm text-brand">
          <Loader2 size={15} className="animate-spin" />
          {t("hardware.applying")}
        </div>
      )}

      {installState === "done" && (
        <div className="flex items-center gap-2 text-sm text-success">
          <CheckCircle size={15} />
          {t("hardware.providerApplied")}
        </div>
      )}

      {installState === "error" && (
        <div className="flex items-center gap-2 text-sm text-danger">
          <AlertCircle size={15} />
          {t("hardware.error")}
        </div>
      )}

      {/* Confirmación si hay indexación activa (aviso real → naranja semántico) */}
      {showRestartConfirm && (
        <div className="mt-3 bg-warning-soft border border-warning/30 rounded-xl p-4">
          <p className="text-sm text-warning mb-3">{t("hardware.indexingWarning")}</p>
          <div className="flex gap-2">
            <Button variant="warning" size="lg" className="flex-1" onClick={() => handleRestart(true)}>
              {t("hardware.pauseAndApply")}
            </Button>
            <Button variant="neutral" size="lg" className="flex-1" onClick={() => setShowRestartConfirm(false)}>
              {t("hardware.wait")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
