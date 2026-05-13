import api from "./client.js";

export const getSources = () => api.get("/sources");
export const addSource = (data) => api.post("/sources", data);
export const deleteSource = (id) => api.delete(`/sources/${id}`);
