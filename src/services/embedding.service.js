/*******************************************************************************
NOMBRE DEL DOCUMENTO: embedding.service.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Servicio de embeddings (stub con extension preparada para HuggingFace).
*******************************************************************************/

import crypto from "crypto";
import { env } from "../config/env.js";

/**
 * Ejecuta la operacion pseudoVectorFromText.
* @param {any} text - Parametro de entrada para la operacion
* @param {any} dims - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
const pseudoVectorFromText = (text, dims = 32) => {
  const hash = crypto.createHash("sha256").update(text).digest();
  const vector = [];
  for (let i = 0; i < dims; i += 1) {
    vector.push(((hash[i] || 0) / 255) * 2 - 1);
  }
  return vector;
};

export const embeddingService = {
  /**
   * Ejecuta la operacion embed.
  * @param {any} text - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async embed(text) {
    if (env.embeddingProvider === "stub") {
      return pseudoVectorFromText(text);
    }

    if (!env.embeddingApiUrl) {
      throw new Error("EMBEDDING_API_URL no configurado para proveedor externo");
    }

    // Placeholder para llamada HTTP a microservicio Python (SentenceTransformers).
    return pseudoVectorFromText(text);
  }
};


