/*******************************************************************************
NOMBRE DEL DOCUMENTO: server.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Punto de entrada del servidor HTTP.
*******************************************************************************/

import app from "./app.js";
import { env } from "./config/env.js";
import { startIngestionWorker } from "./jobs/workers/ingestion.worker.js";

app.listen(env.port, () => {
  // Se inicia tambien el worker local para facilitar desarrollo inicial.
  startIngestionWorker();
  console.log(`API ejecutandose en puerto ${env.port}`);
});


