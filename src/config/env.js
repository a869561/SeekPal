/*******************************************************************************
NOMBRE DEL DOCUMENTO: env.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Carga y normalizacion de variables de entorno.
*******************************************************************************/

import dotenv from "dotenv";

dotenv.config();

export const env = {
  nodeEnv: process.env.NODE_ENV || "development",
  port: Number(process.env.PORT || 3000),
  jwtSecret: process.env.JWT_SECRET || "change_me",
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || "8h",
  redisHost: process.env.REDIS_HOST || "localhost",
  redisPort: Number(process.env.REDIS_PORT || 6379),
  redisPassword: process.env.REDIS_PASSWORD || undefined,
  s3Region: process.env.S3_REGION || "eu-west-1",
  s3Bucket: process.env.S3_BUCKET || "enterprise-smart-search",
  s3Endpoint: process.env.S3_ENDPOINT || undefined,
  s3AccessKeyId: process.env.S3_ACCESS_KEY_ID || "",
  s3SecretAccessKey: process.env.S3_SECRET_ACCESS_KEY || "",
  s3ForcePathStyle: process.env.S3_FORCE_PATH_STYLE === "true",
  localRepositoryPath: process.env.LOCAL_REPOSITORY_PATH || "./data/repository",
  embeddingProvider: process.env.EMBEDDING_PROVIDER || "stub",
  embeddingApiUrl: process.env.EMBEDDING_API_URL || "",
  embeddingModel: process.env.EMBEDDING_MODEL || "sentence-transformers/all-MiniLM-L6-v2"
};


