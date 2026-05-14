import mongoose from "mongoose";

const sourceSchema = new mongoose.Schema({
  name: { type: String, required: true },
  path: { type: String, required: true, unique: true },
  status: { type: String, enum: ["idle", "scanning", "done", "error"], default: "idle" },
  lastIngested: { type: Date, default: null },
  fileCount: { type: Number, default: 0 },
  autoIndex: { type: Boolean, default: false },
}, { timestamps: true });

export const Source = mongoose.model("Source", sourceSchema);
