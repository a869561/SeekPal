/*******************************************************************************
NOMBRE DEL DOCUMENTO: index.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Registro centralizado de rutas.
*******************************************************************************/

import { Router } from "express";
import healthRoutes from "./health.routes.js";
import authRoutes from "./auth.routes.js";
import searchRoutes from "./search.routes.js";
import historyRoutes from "./history.routes.js";
import analyticsRoutes from "./analytics.routes.js";
import connectorRoutes from "./connector.routes.js";

const router = Router();

router.use(healthRoutes);
router.use("/api/auth", authRoutes);
router.use("/api/search", searchRoutes);
router.use("/api/history", historyRoutes);
router.use("/api/analytics", analyticsRoutes);
router.use("/api/connectors", connectorRoutes);

export default router;


