/*******************************************************************************
NOMBRE DEL DOCUMENTO: search.service.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Servicio principal de busqueda semantica (base RAG simplificada).
*******************************************************************************/

import { v4 as uuidv4 } from "uuid";
import { embeddingService } from "./embedding.service.js";
import { historyService } from "./history.service.js";
import { analyticsService } from "./analytics.service.js";
import { enqueueIngestion } from "../jobs/producers/ingestion.producer.js";

const mockKnowledgeBase = [
  {
    id: "doc-1",
    title: "Politica de Seguridad",
    content: "La politica establece controles de acceso, cifrado y auditoria continua.",
    tags: ["seguridad", "cumplimiento"]
  },
  {
    id: "doc-2",
    title: "Manual de RRHH",
    content: "El manual detalla politicas de vacaciones, bajas y evaluaciones anuales.",
    tags: ["rrhh", "procesos"]
  }
];

/**
 * Ejecuta la operacion scoreByKeywordOverlap.
* @param {any} query - Parametro de entrada para la operacion
* @param {any} content - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
const scoreByKeywordOverlap = (query, content) => {
  const q = query.toLowerCase().split(/\s+/);
  const c = content.toLowerCase();
  return q.reduce((acc, term) => (c.includes(term) ? acc + 1 : acc), 0);
};

export const searchService = {
  /**
   * Ejecuta la operacion query.
  * @param {object} options - Parametro de entrada para la operacion
  * @param {any} question - Parametro de entrada para la operacion
  * @param {any} filters - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async query({ userId, question, filters = {} }) {
    await embeddingService.embed(question);

    const filteredDocs = mockKnowledgeBase.filter((doc) => {
      if (!filters.tags || filters.tags.length === 0) return true;
      return filters.tags.some((tag) => doc.tags.includes(tag));
    });

    const ranked = filteredDocs
      .map((doc) => ({
        ...doc,
        score: scoreByKeywordOverlap(question, `${doc.title} ${doc.content}`)
      }))
      .sort((a, b) => b.score - a.score);

    const topChunks = ranked.slice(0, 3);
    const answer =
      topChunks.length > 0
        ? `Segun la base documental, la respuesta probable es: ${topChunks[0].content}`
        : "No se encontraron documentos relevantes para esta consulta.";

    await historyService.addQueryHistory({
      userId,
      query: question,
      filters,
      answer
    });

    await analyticsService.track({
      type: "query",
      metadata: { userId, question, hitCount: topChunks.length }
    });

    return {
      answer,
      references: topChunks.map((item) => ({ id: item.id, title: item.title, score: item.score }))
    };
  },

  /**
   * Ejecuta la operacion enqueueIngestion.
  * @param {object} options - Parametro de entrada para la operacion
  * @param {any} filename - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async enqueueIngestion({ source, filename }) {
    const documentId = uuidv4();
    const job = await enqueueIngestion({ documentId, source, filename });
    return {
      documentId,
      jobId: job.id,
      status: "queued"
    };
  }
};


