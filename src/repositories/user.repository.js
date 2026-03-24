/*******************************************************************************
NOMBRE DEL DOCUMENTO: user.repository.js
AUTOR: Adrián Nasarre
FECHA DE CREACIÓN: 2026-03-24
ÚLTIMA MODIFICACIÓN: 2026-03-24
VERSIÓN: 1.0.0

DESCRIPCIÓN:
Repositorio de usuarios (version en memoria para base inicial).
*******************************************************************************/

const users = new Map();

export const userRepository = {
  /**
   * Ejecuta la operacion findByEmail.
  * @param {any} email - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async findByEmail(email) {
    return users.get(email) || null;
  },

  /**
   * Ejecuta la operacion save.
  * @param {any} user - Parametro de entrada para la operacion
   * @returns {Promise<any>} Resultado de la ejecucion de la funcion
   */
  async save(user) {
    users.set(user.email, user);
    return user;
  }
};


