import mime from "mime-types";

const TEXT_EXTENSIONS = new Set([
  ".txt", ".md", ".markdown", ".html", ".htm", ".css", ".js", ".mjs", ".cjs",
  ".ts", ".tsx", ".jsx", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".toml",
  ".ini", ".cfg", ".conf", ".env", ".sh", ".bat", ".ps1", ".sql", ".csv",
  ".tsv", ".log", ".py", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
  ".cs", ".php", ".rb", ".swift", ".kt", ".r", ".m", ".tex", ".rst",
]);

const DOCUMENT_EXTENSIONS = new Map([
  [".pdf",  { modelIngestible: true }],
  [".docx", { modelIngestible: true }],
  [".doc",  { modelIngestible: false }],
  [".odt",  { modelIngestible: false }],
  [".ods",  { modelIngestible: false }],
  [".odp",  { modelIngestible: false }],
  [".pptx", { modelIngestible: false }],
  [".ppt",  { modelIngestible: false }],
  [".xlsx", { modelIngestible: false }],
  [".xls",  { modelIngestible: false }],
  [".rtf",  { modelIngestible: false }],
  [".epub", { modelIngestible: false }],
]);

const IMAGE_INGESTIBLE = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);
const IMAGE_NON_INGESTIBLE = new Set([".svg", ".bmp", ".tiff", ".tif", ".ico", ".avif"]);

const AUDIO_EXTENSIONS = new Set([
  ".mp3", ".m4a", ".wav", ".ogg", ".oga", ".flac", ".aac", ".wma", ".opus", ".aiff",
]);

const VIDEO_EXTENSIONS = new Set([
  ".mp4", ".avi", ".mpeg", ".mpg", ".mov", ".mkv", ".webm", ".wmv", ".flv", ".m4v", ".3gp",
]);

const ALL_EXTENSIONS = new Set([
  ...TEXT_EXTENSIONS,
  ...DOCUMENT_EXTENSIONS.keys(),
  ...IMAGE_INGESTIBLE,
  ...IMAGE_NON_INGESTIBLE,
  ...AUDIO_EXTENSIONS,
  ...VIDEO_EXTENSIONS,
]);

export function isIndexable(filePath) {
  const ext = filePath.slice(filePath.lastIndexOf(".")).toLowerCase();
  return ALL_EXTENSIONS.has(ext);
}

export function classifyFile(filePath) {
  const ext = filePath.slice(filePath.lastIndexOf(".")).toLowerCase();
  const mimeType = mime.lookup(filePath) || "application/octet-stream";

  if (TEXT_EXTENSIONS.has(ext)) {
    return { category: "text", modelIngestible: true, mimeType };
  }
  if (DOCUMENT_EXTENSIONS.has(ext)) {
    return { category: "document", modelIngestible: DOCUMENT_EXTENSIONS.get(ext).modelIngestible, mimeType };
  }
  if (IMAGE_INGESTIBLE.has(ext)) {
    return { category: "image", modelIngestible: true, mimeType };
  }
  if (IMAGE_NON_INGESTIBLE.has(ext)) {
    return { category: "image", modelIngestible: false, mimeType };
  }
  if (AUDIO_EXTENSIONS.has(ext)) {
    return { category: "audio", modelIngestible: false, mimeType };
  }
  if (VIDEO_EXTENSIONS.has(ext)) {
    return { category: "video", modelIngestible: false, mimeType };
  }
  return { category: "other", modelIngestible: false, mimeType };
}
