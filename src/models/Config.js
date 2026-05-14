import mongoose from "mongoose";

const configSchema = new mongoose.Schema({
  passwordHash: { type: String, required: true },
  settings: {
    theme:    { type: String, default: "auto" },
    fontSize: { type: String, default: "md" },
    language: { type: String, default: "es" },
  },
}, { timestamps: true });

export const Config = mongoose.model("Config", configSchema);
