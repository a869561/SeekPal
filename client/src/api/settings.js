import api from "./client.js";
import { makeSessionCache } from "./sessionCache.js";

// Los ajustes apenas cambian entre visitas, así que se cachean durante la sesión.
// Cualquier guardado los invalida; force=true (espera de reinicio) va a red.
const _settings = makeSessionCache(() => api.get("/settings").then((r) => r.data.data));

export const getSettings = (force = false) => _settings.get(force);
export const invalidateSettingsCache = () => _settings.invalidate();

export const saveSettings = (data) =>
  api.patch("/settings", data).then((r) => {
    _settings.invalidate(); // los ajustes han cambiado
    return r.data.data;
  });
