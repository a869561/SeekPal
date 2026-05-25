import api from "./client.js";

export const getHardwareInfo = () =>
  api.get("/system/hardware").then((r) => r.data.data);

export const getInstallStatus = () =>
  api.get("/system/install-status").then((r) => r.data.data);

export const enableGpu = () =>
  api.post("/system/enable-gpu").then((r) => r.data.data);

export const restartApp = (force = false) =>
  api.post(`/system/restart${force ? "?force=true" : ""}`).then((r) => r.data);
