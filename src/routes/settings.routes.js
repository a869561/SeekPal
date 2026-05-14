import { Router } from "express";
import { verifyToken } from "../middlewares/auth.middleware.js";
import { Config } from "../models/Config.js";
import { ok } from "../utils/api-response.js";

const router = Router();
router.use(verifyToken);

const ALLOWED = new Set(["theme", "fontSize", "language"]);

router.get("/", async (_req, res, next) => {
  try {
    const config = await Config.findOne().lean();
    res.json({ success: true, data: config?.settings ?? {} });
  } catch (err) { next(err); }
});

router.patch("/", async (req, res, next) => {
  try {
    const patch = {};
    for (const [k, v] of Object.entries(req.body)) {
      if (ALLOWED.has(k)) patch[`settings.${k}`] = v;
    }
    const config = await Config.findOneAndUpdate({}, { $set: patch }, { new: true });
    return ok(res, config.settings);
  } catch (err) { next(err); }
});

export default router;
