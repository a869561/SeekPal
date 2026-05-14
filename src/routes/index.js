import { Router } from "express";
import healthRoutes from "./health.routes.js";
import authRoutes from "./auth.routes.js";
import sourcesRoutes from "./sources.routes.js";
import statsRoutes from "./stats.routes.js";
import systemRoutes from "./system.routes.js";

const router = Router();

router.use(healthRoutes);
router.use("/api/auth", authRoutes);
router.use("/api/sources", sourcesRoutes);
router.use("/api/stats", statsRoutes);
router.use(systemRoutes);

export default router;
