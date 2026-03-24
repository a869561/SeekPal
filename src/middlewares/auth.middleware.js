/*******************************************************************************
NOMBRE DEL DOCUMENTO: auth.middleware.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Middleware de autenticacion JWT.
*******************************************************************************/

import jwt from "jsonwebtoken";
import { env } from "../config/env.js";

/**
 * Ejecuta la operacion authRequired.
* @param {any} req - Parametro de entrada para la operacion
* @param {any} res - Parametro de entrada para la operacion
* @param {any} next - Parametro de entrada para la operacion
 * @returns {any} Resultado de la ejecucion de la funcion
 */
export const authRequired = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return res.status(401).json({ success: false, message: "Token no proporcionado" });
  }

  const token = authHeader.split(" ")[1];
  try {
    const decoded = jwt.verify(token, env.jwtSecret);
    req.user = decoded;
    return next();
  } catch (_error) {
    return res.status(401).json({ success: false, message: "Token invalido o expirado" });
  }
};


