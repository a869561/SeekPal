/*******************************************************************************
NOMBRE DEL DOCUMENTO: search.routes.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Rutas de busqueda e ingestion.
*******************************************************************************/

import { Router } from "express";
import { searchController } from "../controllers/search.controller.js";
import { authRequired } from "../middlewares/auth.middleware.js";

const router = Router();

router.post("/query", authRequired, searchController.query);
router.post("/ingest", authRequired, searchController.ingest);

export default router;


