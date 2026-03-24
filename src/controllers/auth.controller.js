/*******************************************************************************
NOMBRE DEL DOCUMENTO: auth.controller.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Controlador de autenticacion.
*******************************************************************************/

import { authService } from "../services/auth.service.js";
import { created, ok } from "../utils/api-response.js";

export const authController = {
  /**
   * Ejecuta la operacion register.
  * @param {any} req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async register(req, res, next) {
    try {
      const user = await authService.register(req.body);
      return created(res, user, "Usuario registrado");
    } catch (error) {
      return next(error);
    }
  },

  /**
   * Ejecuta la operacion login.
  * @param {any} req - Parametro de entrada para la operacion
  * @param {any} res - Parametro de entrada para la operacion
  * @param {any} next - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async login(req, res, next) {
    try {
      const token = await authService.login(req.body);
      return ok(res, token, "Login correcto");
    } catch (error) {
      return next(error);
    }
  }
};


