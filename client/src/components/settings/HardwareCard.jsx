import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Cpu, MemoryStick, Monitor, CheckCircle, AlertCircle, Loader2, RefreshCw, Zap } from "lucide-react";
import { getHardwareInfo, getInstallStatus, enableGpu, restartApp } from "../../api/system.js";

// Icono de tarjeta gráfica (lucide no tiene uno específico, usamos Monitor con variante)
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
  const [installState, setInstallState] = useState("idle"); // idle | installing | done | error | restarting
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);

  const fetchHardware = useCallback(async () => {
    try {
      const data = await getHardwareInfo();
      setHw(data);
    } catch {
      // Ignorar errores de red — la card simplemente no muestra datos
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHardware();
  }, [fetchHardware]);

  // Polling del estado de instalación cuando está en progreso
  useEffect(() => {
    if (installState !== "installing") return;
    const interval = setInterval(async () => {
      try {
        const status = await getInstallStatus();
        if (status.status === "done") {
          setInstallState("restarting");
          clearInterval(interval);
          // SeekPal se reinicia solo; esperar a que vuelva
          waitForRestart();
        } else if (status.status === "error") {
          setInstallState("error");
          clearInterval(interval);
        }
      } catch { /* esperar */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [installState]);

  // Espera a que el backend vuelva tras reinicio
  const waitForRestart = async () => {
    await new Promise((r) => setTimeout(r, 2000));
    for (let i = 0; i < 30; i++) {
      try {
        await getHardwareInfo();
        setInstallState("done");
        await fetchHardware();
        return;
      } catch {
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    setInstallState("error");
  };

  // Arrancar instalación GPU
  const handleEnableGpu = async () => {
    setInstallState("installing");
    try {
      await enableGpu();
    } catch (err) {
      if (err.response?.status === 409) {
        // Ingesta activa — mostrar confirmación de reinicio
        setShowRestartConfirm(true);
        setInstallState("idle");
      } else {
        setInstallState("error");
      }
    }
  };

  // Reiniciar (después de instalar manualmente)
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
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
        <div className="flex items-center gap-2">
          <Loader2 size={18} className="text-indigo-500 animate-spin" />
          <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("hardware.title")}</h2>
        </div>
      </div>
    );
  }

  if (!hw) return null;

  const isGpuActive = hw.active_provider !== "CPUExecutionProvider";
  const hasGpu = hw.gpus && hw.gpus.length > 0;

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 shadow-sm">
      {/* Cabecera */}
      <div className="flex items-center gap-2 mb-5">
        <Zap size={18} className="text-indigo-500" />
        <h2 className="font-semibold text-slate-800 dark:text-slate-100">{t("hardware.title")}</h2>
      </div>

      {/* Lista de componentes */}
      <div className="space-y-2 mb-5">
        {/* CPU */}
        <div className="flex items-start gap-3">
          <Cpu size={16} className="text-slate-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t("hardware.cpu")}</div>
            <div className="text-sm text-slate-700 dark:text-slate-200">{hw.cpu || t("hardware.unknown")}</div>
          </div>
        </div>

        {/* RAM */}
        <div className="flex items-start gap-3">
          <MemoryStick size={16} className="text-slate-400 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t("hardware.ram")}</div>
            <div className="text-sm text-slate-700 dark:text-slate-200">{hw.ram_gb} GB</div>
          </div>
        </div>

        {/* GPUs */}
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

      {/* Estado de procesamiento IA */}
      <div className={`rounded-xl p-3 mb-4 flex items-center gap-3 ${
        isGpuActive
          ? "bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800"
          : hasGpu
            ? "bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800"
            : "bg-slate-50 dark:bg-slate-700/30 border border-slate-200 dark:border-slate-600"
      }`}>
        {isGpuActive
          ? <CheckCircle size={16} className="text-emerald-500 shrink-0" />
          : hasGpu
            ? <AlertCircle size={16} className="text-amber-500 shrink-0" />
            : <Cpu size={16} className="text-slate-400 shrink-0" />
        }
        <div>
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{t("hardware.aiProcessing")}</div>
          <div className={`text-sm font-medium ${
            isGpuActive ? "text-emerald-700 dark:text-emerald-400"
            : hasGpu ? "text-amber-700 dark:text-amber-400"
            : "text-slate-600 dark:text-slate-300"
          }`}>
            {isGpuActive
              ? `${t("hardware.gpu")} ${hw.active_gpu_index != null ? hw.active_gpu_index + 1 : ""} — ${hw.active_label}`
              : hasGpu
                ? t("hardware.cpuFallback")
                : t("hardware.cpuOnly")
            }
          </div>
        </div>
      </div>

      {/* Botón de acción */}
      {installState === "installing" && (
        <div className="flex items-center gap-2 text-sm text-indigo-600 dark:text-indigo-400">
          <Loader2 size={15} className="animate-spin" />
          {t("hardware.downloading")}
        </div>
      )}

      {installState === "restarting" && (
        <div className="flex items-center gap-2 text-sm text-indigo-600 dark:text-indigo-400">
          <Loader2 size={15} className="animate-spin" />
          {t("hardware.applying")}
        </div>
      )}

      {installState === "done" && (
        <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
          <CheckCircle size={15} />
          {t("hardware.done")}
        </div>
      )}

      {installState === "error" && (
        <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
          <AlertCircle size={15} />
          {t("hardware.error")}
        </div>
      )}

      {installState === "idle" && !isGpuActive && hasGpu && hw.recommendation && (
        <button
          onClick={handleEnableGpu}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-medium transition"
        >
          <Zap size={15} />
          {t("hardware.enableGpu")}
        </button>
      )}

      {/* Modal de confirmación si hay indexación activa */}
      {showRestartConfirm && (
        <div className="mt-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-700 rounded-xl p-4">
          <p className="text-sm text-amber-800 dark:text-amber-300 mb-3">{t("hardware.indexingWarning")}</p>
          <div className="flex gap-2">
            <button
              onClick={() => handleRestart(true)}
              className="flex-1 py-2 px-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium transition"
            >
              {t("hardware.pauseAndApply")}
            </button>
            <button
              onClick={() => setShowRestartConfirm(false)}
              className="flex-1 py-2 px-3 rounded-xl border border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 text-sm font-medium transition hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              {t("hardware.wait")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
