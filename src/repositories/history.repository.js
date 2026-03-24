/*******************************************************************************
NOMBRE DEL DOCUMENTO: history.repository.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Repositorio de historial de consultas (in-memory).
*******************************************************************************/

const historyStore = [];

export const historyRepository = {
  /**
   * Ejecuta la operacion add.
  * @param {any} entry - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async add(entry) {
    historyStore.push(entry);
    return entry;
  },

  /**
   * Ejecuta la operacion listByUser.
  * @param {any} userId - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listByUser(userId) {
    return historyStore.filter((item) => item.userId === userId);
  }
};


