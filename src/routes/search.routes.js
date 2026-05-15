import { Router } from "express";
import { searchController } from "../controllers/search.controller.js";
import { verifyToken } from "../middlewares/auth.middleware.js";

const router = Router();

router.get("/", verifyToken, searchController.search);

export default router;
