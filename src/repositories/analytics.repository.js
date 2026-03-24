/*******************************************************************************
NOMBRE DEL DOCUMENTO: analytics.repository.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Repositorio basico de eventos de analitica (in-memory).
*******************************************************************************/

const analyticsEvents = [];

export const analyticsRepository = {
  /**
   * Ejecuta la operacion track.
  * @param {any} event - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async track(event) {
    analyticsEvents.push(event);
    return event;
  },

  /**
   * Ejecuta la operacion getSummary.
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async getSummary() {
    const totalQueries = analyticsEvents.filter((e) => e.type === "query").length;
    const totalIngestions = analyticsEvents.filter((e) => e.type === "ingestion").length;
    return {
      totalEvents: analyticsEvents.length,
      totalQueries,
      totalIngestions
    };
  }
};


