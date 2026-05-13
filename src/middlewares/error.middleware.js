export const notFoundHandler = (req, res) => {
  res.status(404).json({ success: false, message: `Ruta no encontrada: ${req.originalUrl}` });
};

export const globalErrorHandler = (error, _req, res, _next) => {
  const status = error.statusCode || 500;
  if (status === 500) console.error(error);
  res.status(status).json({ success: false, message: error.message || "Error interno del servidor" });
};
