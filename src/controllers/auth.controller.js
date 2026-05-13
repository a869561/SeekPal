import { authService } from "../services/auth.service.js";
import { ok } from "../utils/api-response.js";

export const authController = {
  async login(req, res, next) {
    try {
      const token = await authService.login(req.body);
      return ok(res, token, "Login correcto");
    } catch (error) {
      return next(error);
    }
  },

  async changePassword(req, res, next) {
    try {
      await authService.changePassword(req.body);
      return ok(res, null, "Contraseña actualizada");
    } catch (error) {
      return next(error);
    }
  },
};
