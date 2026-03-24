/*******************************************************************************
NOMBRE DEL DOCUMENTO: ingestion.worker.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Worker de ingestion (parseo/chunking/embedding - base).
*******************************************************************************/

import { Worker } from "bullmq";
import { redisConnection } from "../../config/redis.js";
import { ingestionQueueName } from "../queues.js";
import { analyticsService } from "../../services/analytics.service.js";

let workerInstance = null;

/**
 * Ejecuta la operacion startIngestionWorker.
 * @returns {any} Resultado de la ejecucion de la funcion
 */
export const startIngestionWorker = () => {
  if (workerInstance) {
    return workerInstance;
  }

  workerInstance = new Worker(
    ingestionQueueName,
    async (job) => {
      // Placeholder de procesamiento real de documentos.
      const { documentId, source, filename } = job.data;

      await analyticsService.track({
        type: "ingestion",
        metadata: { documentId, source, filename, status: "processed_stub" }
      });

      return {
        documentId,
        status: "processed_stub"
      };
    },
    { connection: redisConnection }
  );

  workerInstance.on("completed", (job) => {
    console.log(`Ingestion completada para job ${job.id}`);
  });

  workerInstance.on("failed", (job, error) => {
    console.error(`Ingestion fallida para job ${job?.id}`, error);
  });

  return workerInstance;
};


