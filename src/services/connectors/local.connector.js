/*******************************************************************************
NOMBRE DEL DOCUMENTO: local.connector.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Conector para repositorio documental local.
*******************************************************************************/

import fs from "fs/promises";
import path from "path";
import { env } from "../../config/env.js";

export const localConnector = {
  name: "local",

  /**
   * Ejecuta la operacion listDocuments.
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listDocuments() {
    const basePath = path.resolve(env.localRepositoryPath);
    const entries = await fs.readdir(basePath, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile())
      .map((entry) => ({ id: entry.name, name: entry.name, source: "local" }));
  }
};


