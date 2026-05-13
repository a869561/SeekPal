import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { env } from "../config/env.js";
import { Config } from "../models/Config.js";

async function getConfig() {
  let config = await Config.findOne();
  if (!config) {
    const passwordHash = await bcrypt.hash(env.defaultPassword, 10);
    config = await Config.create({ passwordHash });
    console.log(`Contraseña por defecto inicializada: "${env.defaultPassword}"`);
  }
  return config;
}

export const authService = {
  async login({ password }) {
    const config = await getConfig();
    const valid = await bcrypt.compare(password, config.passwordHash);
    if (!valid) {
      const err = new Error("Contraseña incorrecta");
      err.statusCode = 401;
      throw err;
    }
    const token = jwt.sign({ sub: "seekpal" }, env.jwtSecret, { expiresIn: env.jwtExpiresIn });
    return { accessToken: token, tokenType: "Bearer", expiresIn: env.jwtExpiresIn };
  },

  async changePassword({ currentPassword, newPassword }) {
    const config = await getConfig();
    const valid = await bcrypt.compare(currentPassword, config.passwordHash);
    if (!valid) {
      const err = new Error("Contraseña actual incorrecta");
      err.statusCode = 401;
      throw err;
    }
    config.passwordHash = await bcrypt.hash(newPassword, 10);
    await config.save();
  },
};
