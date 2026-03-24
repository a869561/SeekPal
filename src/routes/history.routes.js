/*******************************************************************************
NOMBRE DEL DOCUMENTO: history.routes.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Rutas de historial.
*******************************************************************************/

import { Router } from "express";
import { historyController } from "../controllers/history.controller.js";
import { authRequired } from "../middlewares/auth.middleware.js";

const router = Router();

router.get("/", authRequired, historyController.listMine);

export default router;


