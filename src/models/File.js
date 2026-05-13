import mongoose from "mongoose";

const fileSchema = new mongoose.Schema({
  sourceId: { type: mongoose.Schema.Types.ObjectId, ref: "Source", required: true, index: true },
  name: { type: String, required: true },
  path: { type: String, required: true },
  extension: { type: String, default: "" },
  mimeType: { type: String, default: "application/octet-stream" },
  category: {
    type: String,
    enum: ["text", "document", "image", "audio", "video", "other"],
    default: "other",
  },
  modelIngestible: { type: Boolean, default: false },
  size: { type: Number, default: 0 },
  createdAt: { type: Date },
  modifiedAt: { type: Date },
  metadata: {
    // text / document
    wordCount: Number,
    charCount: Number,
    // image
    width: Number,
    height: Number,
    ppi: Number,
    // audio
    duration: Number,
    bitrate: Number,
    // video
    fps: Number,
  },
}, { timestamps: false });

fileSchema.index({ sourceId: 1, path: 1 }, { unique: true });

export const File = mongoose.model("File", fileSchema);
