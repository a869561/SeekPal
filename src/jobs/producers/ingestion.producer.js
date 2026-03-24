/*******************************************************************************
NOMBRE DEL DOCUMENTO: ingestion.producer.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Productor de jobs de ingestion documental.
*******************************************************************************/

import { ingestionQueue } from "../queues.js";

/**
 * Ejecuta la operacion enqueueIngestion.
* @param {any} payload - Parametro de entrada para la operacion
 * @returns {Promise<any>} Resultado de la ejecucion de la funcion
 */
export const enqueueIngestion = async (payload) => {
  return ingestionQueue.add("ingest-document", payload);
};


