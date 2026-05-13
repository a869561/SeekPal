import jwt from "jsonwebtoken";
import { env } from "../config/env.js";

export const verifyToken = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    return res.status(401).json({ success: false, message: "Token no proporcionado" });
  }
  try {
    req.user = jwt.verify(authHeader.split(" ")[1], env.jwtSecret);
    return next();
  } catch {
    return res.status(401).json({ success: false, message: "Token inválido o expirado" });
  }
};
