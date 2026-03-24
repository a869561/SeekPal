/*******************************************************************************
NOMBRE DEL DOCUMENTO: connector.routes.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Rutas de conectores.
*******************************************************************************/

import { Router } from "express";
import { connectorController } from "../controllers/connector.controller.js";
import { authRequired } from "../middlewares/auth.middleware.js";

const router = Router();

router.get("/", authRequired, connectorController.listSources);
router.get("/:source/documents", authRequired, connectorController.listDocuments);

export default router;


