import api from "./client.js";

export const search = (params) => api.get("/search", { params });
