/*******************************************************************************
NOMBRE DEL DOCUMENTO: history.controller.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Controlador de historial de consultas.
*******************************************************************************/

import { ok } from "../utils/api-response.js";
import { historyService } from "../services/history.service.js";

export const historyController = {
  /**
   * Ejecuta la operacion listMine.
  * @param {any} req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listMine(req, res, next) {
    try {
      const userId = req.user?.sub;
      const items = await historyService.listByUser(userId);
      return ok(res, { items }, "Historial recuperado");
    } catch (error) {
      return next(error);
    }
  }
};


