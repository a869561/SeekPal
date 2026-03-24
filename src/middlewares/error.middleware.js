/*******************************************************************************
NOMBRE DEL DOCUMENTO: error.middleware.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Middlewares de errores centralizados.
*******************************************************************************/

/**
 * Ejecuta la operacion notFoundHandler.
* @param {any} req - Parametro de entrada para la operacion
* @param {any} res - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
export const notFoundHandler = (req, res) => {
  return res.status(404).json({ success: false, message: `Ruta no encontrada: ${req.originalUrl}` });
};

/**
 * Ejecuta la operacion globalErrorHandler.
* @param {any} error - Parametro de entrada para la operacion
* @param {any} _req - Parametro de entrada para la operacion
* @param {any} res - Parametro de entrada para la operacion
* @param {any} _next - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
export const globalErrorHandler = (error, _req, res, _next) => {
  console.error(error);
  return res.status(error.statusCode || 500).json({
    success: false,
    message: error.message || "Error interno"
  });
};


