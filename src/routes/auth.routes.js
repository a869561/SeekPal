import { Router } from "express";
import { authController } from "../controllers/auth.controller.js";
import { verifyToken } from "../middlewares/auth.middleware.js";

const router = Router();

router.post("/login", authController.login);
router.post("/change-password", verifyToken, authController.changePassword);

export default router;
