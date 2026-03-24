/*******************************************************************************
NOMBRE DEL DOCUMENTO: analytics.service.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Servicio de analitica de uso.
*******************************************************************************/

import { analyticsRepository } from "../repositories/analytics.repository.js";

export const analyticsService = {
  /**
   * Ejecuta la operacion track.
  * @param {any} event - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async track(event) {
    return analyticsRepository.track({
      ...event,
      createdAt: new Date().toISOString()
    });
  },

  /**
   * Ejecuta la operacion getSummary.
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async getSummary() {
    return analyticsRepository.getSummary();
  }
};


