import { Router } from "express";
import { sourcesController } from "../controllers/sources.controller.js";
import { verifyToken } from "../middlewares/auth.middleware.js";

const router = Router();

router.use(verifyToken);
router.get("/", sourcesController.list);
router.post("/", sourcesController.add);
router.delete("/:id", sourcesController.remove);
router.post("/:id/ingest", sourcesController.ingest);

export default router;
