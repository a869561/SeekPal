import mongoose from "mongoose";

const configSchema = new mongoose.Schema({
  passwordHash: { type: String, required: true },
}, { timestamps: true });

export const Config = mongoose.model("Config", configSchema);
