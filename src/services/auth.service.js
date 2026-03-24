/*******************************************************************************
NOMBRE DEL DOCUMENTO: auth.service.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Servicio de autenticacion y gestion de credenciales.
*******************************************************************************/

import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { v4 as uuidv4 } from "uuid";
import { env } from "../config/env.js";
import { userRepository } from "../repositories/user.repository.js";

export const authService = {
  /**
   * Ejecuta la operacion register.
  * @param {object} options - Parametro de entrada para la operacion
  * @param {any} password - Parametro de entrada para la operacion
  * @param {any} role - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async register({ email, password, role = "user" }) {
    const existing = await userRepository.findByEmail(email);
    if (existing) {
      const error = new Error("El usuario ya existe");
      error.statusCode = 409;
      throw error;
    }

    const passwordHash = await bcrypt.hash(password, 10);
    const user = { id: uuidv4(), email, passwordHash, role, createdAt: new Date().toISOString() };
    await userRepository.save(user);

    return { id: user.id, email: user.email, role: user.role };
  },

  /**
   * Ejecuta la operacion login.
  * @param {object} options - Parametro de entrada para la operacion
  * @param {any} password - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async login({ email, password }) {
    const user = await userRepository.findByEmail(email);
    if (!user) {
      const error = new Error("Credenciales invalidas");
      error.statusCode = 401;
      throw error;
    }

    const valid = await bcrypt.compare(password, user.passwordHash);
    if (!valid) {
      const error = new Error("Credenciales invalidas");
      error.statusCode = 401;
      throw error;
    }

    const token = jwt.sign({ sub: user.id, email: user.email, role: user.role }, env.jwtSecret, {
      expiresIn: env.jwtExpiresIn
    });

    return {
      accessToken: token,
      tokenType: "Bearer",
      expiresIn: env.jwtExpiresIn
    };
  }
};


