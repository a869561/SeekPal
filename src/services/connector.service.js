/*******************************************************************************
NOMBRE DEL DOCUMENTO: connector.service.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Servicio para orquestar conectores de repositorios.
*******************************************************************************/

import { localConnector } from "./connectors/local.connector.js";
import { s3Connector } from "./connectors/s3.connector.js";
import { gdriveConnector } from "./connectors/gdrive.connector.js";

const connectorMap = {
  local: localConnector,
  s3: s3Connector,
  gdrive: gdriveConnector
};

export const connectorService = {
  /**
   * Ejecuta la operacion listAvailableConnectors.
   * @returns {any} Resultado de la ejecucion de la funcion
   */
  listAvailableConnectors() {
    return Object.keys(connectorMap);
  },

  /**
   * Ejecuta la operacion listDocuments.
  * @param {any} source - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listDocuments(source) {
    const connector = connectorMap[source];
    if (!connector) {
      const error = new Error(`Conector no soportado: ${source}`);
      error.statusCode = 400;
      throw error;
    }
    return connector.listDocuments();
  }
};


