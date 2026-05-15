import fs from "fs/promises";
import path from "path";
import { Source } from "../models/Source.js";
import { File } from "../models/File.js";
import { classifyFile, isIndexable } from "../utils/mime-classifier.js";
import { extractMetadata } from "../utils/metadata-extractor.js";

const IGNORED_DIRS  = new Set(["node_modules", ".git", "__pycache__", ".venv", "venv", "dist", ".next"]);
const IGNORED_FILES = new Set(["desktop.ini", "thumbs.db", "thumbs.db:encryptable", ".ds_store", "ntuser.dat", "ntuser.ini"]);
const CONCURRENCY   = 8;

function isHidden(name) {
  return name.startsWith(".") || name.startsWith("$");
}

async function walkDir(dirPath) {
  try {
    const items = await fs.readdir(dirPath, { withFileTypes: true });
    const results = await Promise.all(
      items.map((item) => {
        if (isHidden(item.name)) return [];
        if (item.isDirectory()) {
          if (IGNORED_DIRS.has(item.name)) return [];
          return walkDir(path.join(dirPath, item.name));
        }
        if (item.isFile()) {
          if (IGNORED_FILES.has(item.name.toLowerCase())) return [];
          const filePath = path.join(dirPath, item.name);
          if (!isIndexable(filePath)) return [];
          return [filePath];
        }
        return [];
      })
    );
    return results.flat();
  } catch {
    return [];
  }
}

async function processFile(sourceId, filePath) {
  const stat = await fs.stat(filePath);
  const ext = path.extname(filePath).toLowerCase();
  const { category, mimeType } = classifyFile(filePath);
  const metadata = await extractMetadata(filePath, category, ext);
  return {
    sourceId,
    name: path.basename(filePath),
    path: filePath,
    extension: ext,
    mimeType,
    category,
    size: stat.size,
    createdAt: stat.birthtime,
    modifiedAt: stat.mtime,
    metadata,
  };
}

export async function ingestSource(sourceId, onProgress) {
  const source = await Source.findById(sourceId);
  if (!source) throw new Error("Fuente no encontrada");

  await Source.findByIdAndUpdate(sourceId, { status: "scanning" });

  try {
    const allPaths = await walkDir(source.path);
    const total = allPaths.length;

    await File.deleteMany({ sourceId });

    let processed = 0;

    for (let i = 0; i < allPaths.length; i += CONCURRENCY) {
      const chunk = allPaths.slice(i, i + CONCURRENCY);

      const settled = await Promise.allSettled(
        chunk.map((filePath) => processFile(sourceId, filePath))
      );

      const ops = [];
      for (let j = 0; j < settled.length; j++) {
        const filePath = chunk[j];
        processed++;
        if (settled[j].status === "fulfilled") {
          const doc = settled[j].value;
          ops.push({
            updateOne: {
              filter: { sourceId, path: filePath },
              update: { $set: doc },
              upsert: true,
            },
          });
        }
        onProgress({ current: processed, total, file: path.basename(filePath) });
      }

      if (ops.length) await File.bulkWrite(ops, { ordered: false });
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
