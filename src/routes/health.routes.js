import { Router } from "express";
import mongoose from "mongoose";

const router = Router();

router.get("/health", (_req, res) => {
  const db = mongoose.connection.readyState === 1 ? "up" : "down";
  res.status(200).json({ success: true, status: "up", db, timestamp: new Date().toISOString() });
});

export default router;

