import fs from "fs";
import { Source } from "../models/Source.js";
import { ingestSource } from "./scanner.service.js";

const DEBOUNCE_MS = 10_000;

const watchers = new Map();   // sourceId → FSWatcher
const timers   = new Map();   // sourceId → debounce timer

function scheduleIngest(sourceId) {
  if (timers.has(sourceId)) clearTimeout(timers.get(sourceId));
  const t = setTimeout(async () => {
    timers.delete(sourceId);
    try {
      await ingestSource(sourceId, () => {});
      console.log(`[watcher] auto-reindexed source ${sourceId}`);
    } catch (err) {
      console.error(`[watcher] error re-indexing ${sourceId}:`, err.message);
    }
  }, DEBOUNCE_MS);
  timers.set(sourceId, t);
}

export function startWatcher(sourceId, dirPath) {
  if (watchers.has(sourceId)) return;
  try {
    const watcher = fs.watch(dirPath, { recursive: true }, () => {
      scheduleIngest(sourceId);
    });
    watcher.on("error", () => stopWatcher(sourceId));
    watchers.set(sourceId, watcher);
    console.log(`[watcher] watching ${dirPath}`);
  } catch (err) {
    console.error(`[watcher] cannot watch ${dirPath}:`, err.message);
  }
}

export function stopWatcher(sourceId) {
  if (timers.has(sourceId)) { clearTimeout(timers.get(sourceId)); timers.delete(sourceId); }
  if (watchers.has(sourceId)) { watchers.get(sourceId).close(); watchers.delete(sourceId); }
}

export async function initWatchers() {
  const sources = await Source.find({ autoIndex: true });
  for (const s of sources) startWatcher(String(s._id), s.path);
  console.log(`[watcher] ${sources.length} watcher(s) inicializados`);
}
