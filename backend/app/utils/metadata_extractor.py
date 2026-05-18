"""Extracción de metadatos por categoría de fichero.

Cada extractor es resistente a errores: ante cualquier excepción devuelve un
diccionario vacío para no abortar la ingesta de toda una fuente.
"""

import re
import zipfile
from pathlib import Path


def _count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


# --- Texto plano ----------------------------------------------------------

def _text_meta(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    return {"wordCount": _count_words(content), "charCount": len(content)}


# --- PDF ------------------------------------------------------------------

def _pdf_meta(path: Path) -> dict:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return {"wordCount": _count_words(text), "charCount": len(text)}
    except Exception:
        return {}


# --- DOCX -----------------------------------------------------------------

def _docx_meta(path: Path) -> dict:
    try:
        import docx

        document = docx.Document(str(path))
        text = "\n".join(p.text for p in document.paragraphs)
        return {"wordCount": _count_words(text), "charCount": len(text)}
    except Exception:
        return {}


# --- ZIP/XML basados (pptx, odt, odp) ------------------------------------

_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜáéíóúüñÑ]{3,}")


def _zip_text_meta(path: Path, match: callable) -> dict:
    try:
        with zipfile.ZipFile(str(path)) as zf:
            chunks: list[str] = []
            for name in zf.namelist():
                if not match(name):
                    continue
                with zf.open(name) as fh:
                    raw = fh.read().decode("utf-8", errors="ignore")
                chunks.extend(_WORD_RE.findall(raw))
        text = " ".join(chunks)
        return {"wordCount": _count_words(text), "charCount": len(text)}
    except Exception:
        return {}


def _pptx_meta(path: Path) -> dict:
    return _zip_text_meta(path, lambda n: n.startswith("ppt/slides/slide") and n.endswith(".xml"))


def _odt_meta(path: Path) -> dict:
    return _zip_text_meta(path, lambda n: n == "content.xml")


# --- Imágenes -------------------------------------------------------------

def _image_meta(path: Path) -> dict:
    try:
        from PIL import Image

        with Image.open(str(path)) as img:
            width, height = img.size
            dpi = img.info.get("dpi")
            ppi = float(dpi[0]) if isinstance(dpi, tuple) and dpi else None
        return {"width": width, "height": height, "ppi": ppi}
    except Exception:
        return {}


# --- Audio ----------------------------------------------------------------

def _audio_meta(path: Path) -> dict:
    try:
        from mutagen import File as MutagenFile

        mf = MutagenFile(str(path))
        if mf is None or mf.info is None:
            return {}
        info = mf.info
        duration = int(round(getattr(info, "length", 0) or 0))
        bitrate_bps = getattr(info, "bitrate", None)
        bitrate = int(round(bitrate_bps / 1000)) if bitrate_bps else None
        return {"duration": duration, "bitrate": bitrate}
    except Exception:
        return {}


# --- Vídeo (ffprobe vía ffmpeg-python) ------------------------------------

def _video_meta(path: Path) -> dict:
    try:
        import ffmpeg

        probe = ffmpeg.probe(str(path))
    except Exception:
        return {}

    fmt = probe.get("format", {}) or {}
    streams = probe.get("streams", []) or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

    meta: dict = {"duration": int(round(float(fmt.get("duration") or 0)))}
    if video_stream:
        if "width" in video_stream:
            meta["width"] = int(video_stream["width"])
        if "height" in video_stream:
            meta["height"] = int(video_stream["height"])
        frame_rate = video_stream.get("avg_frame_rate") or ""
        if "/" in frame_rate:
            num_s, den_s = frame_rate.split("/", 1)
            try:
                num, den = float(num_s), float(den_s)
                if den:
                    meta["fps"] = round(num / den, 1)
            except ValueError:
                pass
    return meta


# --- Dispatcher -----------------------------------------------------------

def extract(path: str, category: str, extension: str) -> dict:
    p = Path(path)
    ext = extension.lower()
    if category == "text":
        return _text_meta(p)
    if category == "document":
        if ext == ".pdf":
            return _pdf_meta(p)
        if ext == ".docx":
            return _docx_meta(p)
        if ext == ".pptx":
            return _pptx_meta(p)
        if ext in (".odt", ".odp"):
            return _odt_meta(p)
        return {}
    if category == "image":
        return _image_meta(p)
    if category == "audio":
        return _audio_meta(p)
    if category == "video":
        return _video_meta(p)
    return {}
