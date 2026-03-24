/*******************************************************************************
NOMBRE DEL DOCUMENTO: health.routes.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Rutas de salud del sistema.
*******************************************************************************/

import { Router } from "express";

const router = Router();

router.get("/health", (_req, res) => {
  return res.status(200).json({ success: true, status: "up", timestamp: new Date().toISOString() });
});

export default router;


