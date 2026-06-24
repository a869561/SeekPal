import api from "./client.js";
import { makeSessionCache } from "./sessionCache.js";

// Cache de sesión para hardware info (no cambia entre visitas a la página).
// Se invalida con force=true (botón refrescar) o al reiniciar el backend.
const _hw = makeSessionCache(() => api.get("/system/hardware").then((r) => r.data.data));

export const getHardwareInfo = (force = false) => _hw.get(force);
export const invalidateHardwareCache = () => _hw.invalidate();

export const getInstallStatus = () =>
  api.get("/system/install-status").then((r) => r.data.data);

export const enableGpu = () =>
  api.post("/system/enable-gpu").then((r) => r.data.data);

export const setProvider = (provider) =>
  api.post("/system/set-provider", { provider }).then((r) => r.data.data);

export const restartApp = (force = false) =>
  api.post(`/system/restart${force ? "?force=true" : ""}`).then((r) => r.data);

// Abre un fichero indexado (resultado de búsqueda o cita) con la app por
// defecto del SO. Se pasa el file_id, no la ruta.
export const openFile = (fileId) =>
  api.post("/system/open-file", { file_id: fileId }).then((r) => r.data.data);

// Estado de Docling: cacheado durante la sesión. force=true en el polling de
// instalación (que espera ver cambiar el estado) y en el botón refrescar.
const _docling = makeSessionCache(() => api.get("/system/docling-status").then((r) => r.data.data));

export const getDoclingStatus = (force = false) => _docling.get(force);
export const invalidateDoclingCache = () => _docling.invalidate();

export const installDocling = () =>
  api.post("/system/install-docling").then((r) => {
    _docling.invalidate(); // la instalación cambia el estado
    return r.data.data;
  });

// ── Gestión de modelos (panel "Modelos y almacenamiento") ──────────────────

// Lista de modelos: cacheada durante la sesión. La invalidan instalar/borrar y
// el botón refrescar (force=true) la salta para releer tras una descarga.
const _models = makeSessionCache(() => api.get("/system/models").then((r) => r.data.data));

export const getModels = (force = false) => _models.get(force);
export const invalidateModelsCache = () => _models.invalidate();

export const pullModel = (model) =>
  api.post("/system/models/pull", { model }).then((r) => {
    _models.invalidate(); // la lista de instalados cambiará al terminar
    return r.data.data;
  });

export const getModelPullStatus = () =>
  api.get("/system/models/pull-status").then((r) => r.data.data);

export const deleteModel = (model) =>
  api.post("/system/models/delete", { model }).then((r) => {
    _models.invalidate(); // ya no está instalado
    return r.data.data;
  });

// ── Planificador de dispositivos ───────────────────────────────────────────

/** Dry-run del planificador: devuelve el plan resuelto + feasibilidad sin persistir nada.
 *  Body: { processingPriority, deviceOverrides }
 *  Respuesta: { devices, feasible, vram_total_mib, budget_mib, gpu_used_mib, overflow, ollama_gpu_overhead_bytes }
 */
export const planPreview = (config) =>
  api.post("/devices/plan-preview", config).then((r) => r.data.data);
