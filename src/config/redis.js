/*******************************************************************************
NOMBRE DEL DOCUMENTO: redis.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Cliente Redis compartido para BullMQ y cache.
*******************************************************************************/

import IORedis from "ioredis";
import { env } from "./env.js";

export const redisConnection = new IORedis({
  host: env.redisHost,
  port: env.redisPort,
  password: env.redisPassword,
  maxRetriesPerRequest: null
});


