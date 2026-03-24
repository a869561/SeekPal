/*******************************************************************************
NOMBRE DEL DOCUMENTO: api-response.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Helpers estandar para respuestas HTTP.
*******************************************************************************/

/**
 * Ejecuta la operacion ok.
* @param {any} res - Parametro de entrada para la operacion
* @param {any} data - Parametro de entrada para la operacion
* @param {any} message - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
export const ok = (res, data = {}, message = "OK") => {
  return res.status(200).json({ success: true, message, data });
};

/**
 * Ejecuta la operacion created.
* @param {any} res - Parametro de entrada para la operacion
* @param {any} data - Parametro de entrada para la operacion
* @param {any} message - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
export const created = (res, data = {}, message = "Created") => {
  return res.status(201).json({ success: true, message, data });
};


