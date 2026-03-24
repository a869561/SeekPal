/*******************************************************************************
NOMBRE DEL DOCUMENTO: analytics.routes.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Rutas de analitica.
*******************************************************************************/

import { Router } from "express";
import { analyticsController } from "../controllers/analytics.controller.js";
import { authRequired } from "../middlewares/auth.middleware.js";

const router = Router();

router.get("/summary", authRequired, analyticsController.summary);

export default router;


