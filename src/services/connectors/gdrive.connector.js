/*******************************************************************************
NOMBRE DEL DOCUMENTO: gdrive.connector.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Conector Google Drive (placeholder de integracion).
*******************************************************************************/

export const gdriveConnector = {
  name: "gdrive",

  /**
   * Ejecuta la operacion listDocuments.
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listDocuments() {
    return [
      {
        id: "pending-integration",
        name: "Google Drive connector pendiente de OAuth + API",
        source: "gdrive"
      }
    ];
  }
};


