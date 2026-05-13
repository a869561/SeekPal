import api from "./client.js";

export const getSummary = () => api.get("/stats/summary");
export const getFiles = (params) => api.get("/stats/files", { params });
