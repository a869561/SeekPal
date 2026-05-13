import { Router } from "express";
import { statsController } from "../controllers/stats.controller.js";
import { verifyToken } from "../middlewares/auth.middleware.js";

const router = Router();

router.use(verifyToken);
router.get("/summary", statsController.summary);
router.get("/files", statsController.files);

export default router;
