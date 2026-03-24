/*******************************************************************************
NOMBRE DEL DOCUMENTO: connector.controller.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Controlador para conectores de repositorios.
*******************************************************************************/

import { ok } from "../utils/api-response.js";
import { connectorService } from "../services/connector.service.js";

export const connectorController = {
  /**
   * Ejecuta la operacion listSources.
  * @param {any} _req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listSources(_req, res, next) {
    try {
      const connectors = connectorService.listAvailableConnectors();
      return ok(res, { connectors }, "Conectores disponibles");
    } catch (error) {
      return next(error);
    }
  },

  /**
   * Ejecuta la operacion listDocuments.
  * @param {any} req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listDocuments(req, res, next) {
    try {
      const { source } = req.params;
      const documents = await connectorService.listDocuments(source);
      return ok(res, { source, documents }, "Documentos recuperados");
    } catch (error) {
      return next(error);
    }
  }
};


