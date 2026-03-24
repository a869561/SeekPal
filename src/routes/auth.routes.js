/*******************************************************************************
NOMBRE DEL DOCUMENTO: auth.routes.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Rutas de autenticacion.
*******************************************************************************/

import { Router } from "express";
import { authController } from "../controllers/auth.controller.js";

const router = Router();

router.post("/register", authController.register);
router.post("/login", authController.login);

export default router;


