import api from "./client.js";

export const getSettings  = ()     => api.get("/settings").then((r) => r.data.data);
export const saveSettings = (data) => api.patch("/settings", data).then((r) => r.data.data);
