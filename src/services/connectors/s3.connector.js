/*******************************************************************************
NOMBRE DEL DOCUMENTO: s3.connector.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Conector para repositorio en S3.
*******************************************************************************/

import { ListObjectsV2Command } from "@aws-sdk/client-s3";
import { s3Client } from "../../config/s3.js";
import { env } from "../../config/env.js";

export const s3Connector = {
  name: "s3",

  /**
   * Ejecuta la operacion listDocuments.
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async listDocuments() {
    const command = new ListObjectsV2Command({ Bucket: env.s3Bucket, MaxKeys: 200 });
    const result = await s3Client.send(command);
    return (result.Contents || []).map((obj) => ({
      id: obj.Key,
      name: obj.Key,
      source: "s3",
      size: obj.Size,
      updatedAt: obj.LastModified
    }));
  }
};


