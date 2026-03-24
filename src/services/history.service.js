/*******************************************************************************
NOMBRE DEL DOCUMENTO: history.service.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Servicio para guardar y recuperar historial de consultas.
*******************************************************************************/

import { v4 as uuidv4 } from "uuid";
import { historyRepository } from "../repositories/history.repository.js";

export const historyService = {
  /**
   * Ejecuta la operacion addQueryHistory.
  * @param {object} options - Parametro de entrada para la operacion
  * @param {any} query - Parametro de entrada para la operacion
  * @param {any} filters - Parametro de entrada para la operacion
  * @param {any} answer - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async addQueryHistory({ userId, query, filters, answer }) {
    return historyRepository.add({
      id: uuidv4(),
      userId,
      query,
      filters,
      answer,
      createdAt: new Date().toISOString()
    });
  },

  /**
   * Ejecuta la operacion listByUser.
  * @param {any} userId - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listByUser(userId) {
    return historyRepository.listByUser(userId);
  }
};


