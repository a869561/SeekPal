import api from "./client.js";

export const login = (password) => api.post("/auth/login", { password });
export const changePassword = (data) => api.post("/auth/change-password", data);
