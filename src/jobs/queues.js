/*******************************************************************************
NOMBRE DEL DOCUMENTO: queues.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Definicion de colas BullMQ.
*******************************************************************************/

import { Queue } from "bullmq";
import { redisConnection } from "../config/redis.js";

export const ingestionQueueName = "document-ingestion";

export const ingestionQueue = new Queue(ingestionQueueName, {
  connection: redisConnection,
  defaultJobOptions: {
    removeOnComplete: 200,
    removeOnFail: 500,
    attempts: 3,
    backoff: {
      type: "exponential",
      delay: 1000
    }
  }
});


