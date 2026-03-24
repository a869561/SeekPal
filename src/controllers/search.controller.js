/*******************************************************************************
NOMBRE DEL DOCUMENTO: search.controller.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Controlador de busqueda semantica e ingestion.
*******************************************************************************/

import { ok, created } from "../utils/api-response.js";
import { searchService } from "../services/search.service.js";

export const searchController = {
  /**
   * Ejecuta la operacion query.
  * @param {any} req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async query(req, res, next) {
    try {
      const userId = req.user?.sub || "anonymous";
      const { question, filters } = req.body;
      const result = await searchService.query({ userId, question, filters });
      return ok(res, result, "Consulta completada");
    } catch (error) {
      return next(error);
    }
  },

  /**
   * Ejecuta la operacion ingest.
  * @param {any} req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async ingest(req, res, next) {
    try {
      const { source, filename } = req.body;
      const result = await searchService.enqueueIngestion({ source, filename });
      return created(res, result, "Documento encolado para ingestion");
    } catch (error) {
      return next(error);
    }
  }
};


