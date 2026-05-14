import fs from "fs/promises";

function countWords(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

// ── Text ───────────────────────────────────────────────────────────────────

async function extractTextMetadata(filePath) {
  try {
    const content = await fs.readFile(filePath, "utf8");
    return { wordCount: countWords(content), charCount: content.length };
  } catch {
    return {};
  }
}

// ── Documents ──────────────────────────────────────────────────────────────

async function extractDocxMetadata(filePath) {
  try {
    const mammoth = await import("mammoth");
    const result = await mammoth.extractRawText({ path: filePath });
    return { wordCount: countWords(result.value), charCount: result.value.length };
  } catch {
    return {};
  }
}

async function extractPdfMetadata(filePath) {
  try {
    const pdfParse = (await import("pdf-parse")).default;
    const buffer = await fs.readFile(filePath);
    const data = await pdfParse(buffer);
    return { wordCount: countWords(data.text), charCount: data.text.length };
  } catch {
    return {};
  }
}

async function extractZipXmlMetadata(filePath, matchFile) {
  try {
    const JSZip = (await import("jszip")).default;
    const { XMLParser } = await import("fast-xml-parser");
    const buffer = await fs.readFile(filePath);
    const zip = await JSZip.loadAsync(buffer);
    const parser = new XMLParser({ ignoreAttributes: true });

    let fullText = "";
    for (const [name, file] of Object.entries(zip.files)) {
      if (matchFile(name)) {
        const xml = await file.async("string");
        fullText += JSON.stringify(parser.parse(xml)) + " ";
      }
    }
    const strings = fullText.match(/[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{3,}/g) || [];
    const text = strings.join(" ");
    return { wordCount: countWords(text), charCount: text.length };
  } catch {
    return {};
  }
}

async function extractPptxMetadata(filePath) {
  return extractZipXmlMetadata(filePath, (name) => /^ppt\/slides\/slide\d+\.xml$/.test(name));
}

async function extractOdtMetadata(filePath) {
  return extractZipXmlMetadata(filePath, (name) => name === "content.xml");
}

// ── Images ─────────────────────────────────────────────────────────────────

async function extractImageMetadata(filePath) {
  try {
    const sharp = (await import("sharp")).default;
    const meta = await sharp(filePath).metadata();
    return { width: meta.width, height: meta.height, ppi: meta.density || null };
  } catch {
    return {};
  }
}

// ── Audio ──────────────────────────────────────────────────────────────────

async function extractAudioMetadata(filePath) {
  try {
    const mm = await import("music-metadata");
    const meta = await mm.parseFile(filePath, { duration: true });
    return {
      duration: Math.round(meta.format.duration || 0),
      bitrate: meta.format.bitrate ? Math.round(meta.format.bitrate / 1000) : null,
    };
  } catch {
    return {};
  }
}

// ── Video ──────────────────────────────────────────────────────────────────

let _ffmpeg = null;
async function getFFmpeg() {
  if (_ffmpeg) return _ffmpeg;
  const ffmpeg = (await import("fluent-ffmpeg")).default;
  const ffprobeStatic = (await import("ffprobe-static")).default;
  ffmpeg.setFfprobePath(ffprobeStatic.path);
  _ffmpeg = ffmpeg;
  return _ffmpeg;
}

async function extractVideoMetadata(filePath) {
  try {
    const ffmpeg = await getFFmpeg();

    return await new Promise((resolve) => {
      ffmpeg.ffprobe(filePath, (err, data) => {
        if (err) return resolve({});
        const fmt = data.format || {};
        const video = (data.streams || []).find((s) => s.codec_type === "video");
        const meta = { duration: Math.round(parseFloat(fmt.duration) || 0) };
        if (video) {
          meta.width = video.width;
          meta.height = video.height;
          if (video.avg_frame_rate) {
            const [num, den] = video.avg_frame_rate.split("/").map(Number);
            meta.fps = den ? Math.round((num / den) * 10) / 10 : null;
          }
        }
        resolve(meta);
      });
    });
  } catch {
    return {};
  }
}

// ── Dispatcher ─────────────────────────────────────────────────────────────

export async function extractMetadata(filePath, category, extension) {
  switch (category) {
    case "text":     return extractTextMetadata(filePath);
    case "document": {
      const ext = extension.toLowerCase();
      if (ext === ".pdf")               return extractPdfMetadata(filePath);
      if (ext === ".docx")              return extractDocxMetadata(filePath);
      if (ext === ".pptx")              return extractPptxMetadata(filePath);
      if (ext === ".odt" || ext === ".odp") return extractOdtMetadata(filePath);
      return {};
    }
    case "image":  return extractImageMetadata(filePath);
    case "audio":  return extractAudioMetadata(filePath);
    case "video":  return extractVideoMetadata(filePath);
    default:       return {};
  }
}
