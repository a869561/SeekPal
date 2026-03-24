/*******************************************************************************
NOMBRE DEL DOCUMENTO: analytics.controller.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Controlador de analitica de uso.
*******************************************************************************/

import { ok } from "../utils/api-response.js";
import { analyticsService } from "../services/analytics.service.js";

export const analyticsController = {
  /**
   * Ejecuta la operacion summary.
  * @param {any} _req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async summary(_req, res, next) {
    try {
      const summary = await analyticsService.getSummary();
      return ok(res, summary, "Resumen de analitica");
    } catch (error) {
      return next(error);
    }
  }
};


