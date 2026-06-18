import api from "./client.js";

// Cache de sesión para hardware info (no cambia entre visitas a la página).
// Se invalida con force=true (botón refrescar) o al reiniciar el backend.
let _hwCache = null;
let _hwInflight = null;

export const getHardwareInfo = (force = false) => {
  if (!force && _hwCache) return Promise.resolve(_hwCache);
  if (!force && _hwInflight) return _hwInflight;
  _hwInflight = api
    .get("/system/hardware")
    .then((r) => {
      _hwCache = r.data.data;
      return _hwCache;
    })
    .finally(() => { _hwInflight = null; });
  return _hwInflight;
};

export const invalidateHardwareCache = () => { _hwCache = null; };

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

export const getDoclingStatus = () =>
  api.get("/system/docling-status").then((r) => r.data.data);

export const installDocling = () =>
  api.post("/system/install-docling").then((r) => r.data.data);

// ── Gestión de modelos (panel "Modelos y almacenamiento") ──────────────────

export const getModels = () =>
  api.get("/system/models").then((r) => r.data.data);

export const pullModel = (model) =>
  api.post("/system/models/pull", { model }).then((r) => r.data.data);

export const getModelPullStatus = () =>
  api.get("/system/models/pull-status").then((r) => r.data.data);

export const deleteModel = (model) =>
  api.post("/system/models/delete", { model }).then((r) => r.data.data);
