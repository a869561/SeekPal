import fs from "fs/promises";
import path from "path";
import { Source } from "../models/Source.js";
import { File } from "../models/File.js";
import { classifyFile } from "../utils/mime-classifier.js";
import { extractMetadata } from "../utils/metadata-extractor.js";

const IGNORED_DIRS = new Set(["node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".next"]);

async function walkDir(dirPath) {
  const entries = [];
  try {
    const items = await fs.readdir(dirPath, { withFileTypes: true });
    for (const item of items) {
      if (item.isDirectory()) {
        if (IGNORED_DIRS.has(item.name)) continue;
        const sub = await walkDir(path.join(dirPath, item.name));
        entries.push(...sub);
      } else if (item.isFile()) {
        entries.push(path.join(dirPath, item.name));
      }
    }
  } catch {
    // skip unreadable dirs
  }
  return entries;
}

export async function ingestSource(sourceId, onProgress) {
  const source = await Source.findById(sourceId);
  if (!source) throw new Error("Fuente no encontrada");

  await Source.findByIdAndUpdate(sourceId, { status: "scanning" });

  try {
    // Collect all file paths first
    const allPaths = await walkDir(source.path);
    const total = allPaths.length;

    // Remove old files for this source
    await File.deleteMany({ sourceId });

    let processed = 0;
    for (const filePath of allPaths) {
      try {
        const stat = await fs.stat(filePath);
        const ext = path.extname(filePath).toLowerCase();
        const { category, modelIngestible, mimeType } = classifyFile(filePath);
        const metadata = await extractMetadata(filePath, category, ext);

        await File.findOneAndUpdate(
          { sourceId, path: filePath },
          {
            sourceId,
            name: path.basename(filePath),
            path: filePath,
            extension: ext,
            mimeType,
            category,
            modelIngestible,
            size: stat.size,
            createdAt: stat.birthtime,
            modifiedAt: stat.mtime,
            metadata,
          },
          { upsert: true, new: true }
        );
      } catch {
        // skip problematic files
      }

      processed++;
      onProgress({ current: processed, total, file: path.basename(filePath) });
    }

    const fileCount = await File.countDocuments({ sourceId });
    await Source.findByIdAndUpdate(sourceId, {
      status: "done",
      lastIngested: new Date(),
      fileCount,
    });
  } catch (err) {
    await Source.findByIdAndUpdate(sourceId, { status: "error" });
    throw err;
  }
}
