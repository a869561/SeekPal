import api from "./client.js";

export const getSources       = ()     => api.get("/sources");
export const addSource        = (data) => api.post("/sources", data);
export const deleteSource     = (id)   => api.delete(`/sources/${id}`);
export const toggleAutoIndex  = (id)   => api.patch(`/sources/${id}/auto-index`);
export const pauseIngest      = (id)   => api.post(`/sources/${id}/ingest/pause`);
export const resumeIngest     = (id)   => api.post(`/sources/${id}/ingest/resume`);
export const cancelIngest     = (id)   => api.post(`/sources/${id}/ingest/cancel`);
export const getIngestProgress = (id)  => api.get(`/sources/${id}/ingest/progress`);
