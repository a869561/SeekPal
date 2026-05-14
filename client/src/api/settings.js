import api from "./client.js";

export const getSettings  = ()     => api.get("/settings");
export const saveSettings = (data) => api.patch("/settings", data);
