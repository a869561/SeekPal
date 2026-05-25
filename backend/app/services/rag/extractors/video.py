"""Extractor de video: combina audio (Whisper) + frames clave (Moondream caption).

Estrategia simple sin PySceneDetect (mas barato y suficiente para indexar):
  1. ffmpeg extrae la pista de audio a WAV 16 kHz mono -> Whisper transcribe.
  2. ffmpeg samplea 1 frame cada N segundos -> Moondream describe cada frame.
  3. Concatena: transcript + lista de captions con timestamps.

Usa el binario ffmpeg bundleado en `imageio-ffmpeg` (sin depender del PATH).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from app.services.rag.audio_service import transcribe
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.image_service import caption_image
from app.services.rag.types import ExtractedDoc


_FRAME_INTERVAL_SECONDS = int(os.getenv("SEEKPAL_VIDEO_FRAME_INTERVAL", "30"))
_MAX_FRAMES = int(os.getenv("SEEKPAL_VIDEO_MAX_FRAMES", "20"))


def _ffmpeg_bin() -> str:
    """Resuelve el binario ffmpeg bundleado por imageio-ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"  # fallback al sistema


def _extract_audio(video: Path, out_wav: Path) -> bool:
    cmd = [
        _ffmpeg_bin(), "-y", "-loglevel", "error",
        "-i", str(video),
        "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return out_wav.exists() and out_wav.stat().st_size > 1024
    except (subprocess.SubprocessError, OSError):
        return False


def _extract_frames(video: Path, out_dir: Path, interval: int) -> list[Path]:
    cmd = [
        _ffmpeg_bin(), "-y", "-loglevel", "error",
        "-i", str(video),
        "-vf", f"fps=1/{interval}",
        "-frames:v", str(_MAX_FRAMES),
        str(out_dir / "frame_%04d.jpg"),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (subprocess.SubprocessError, OSError):
        return []
    return sorted(out_dir.glob("frame_*.jpg"))


def _timestamp(index: int, interval: int) -> str:
    secs = index * interval
    return f"{secs // 60:02d}:{secs % 60:02d}"


class VideoExtractor(BaseExtractor):
    _EXTENSIONS = [
        ".mp4", ".avi", ".mpeg", ".mpg", ".mov",
        ".mkv", ".webm", ".wmv", ".flv", ".m4v", ".3gp",
    ]

    def extract(self, path: Path) -> ExtractedDoc:
        parts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="seekpal_video_") as tmpdir:
            tmp = Path(tmpdir)

            # 1) Audio -> transcript
            wav = tmp / "audio.wav"
            if _extract_audio(path, wav):
                transcript = transcribe(wav)
                if transcript:
                    parts.append(f"Transcripcion del audio:\n{transcript}")

            # 2) Frames -> captions con timestamp
            frames = _extract_frames(path, tmp, _FRAME_INTERVAL_SECONDS)
            if frames:
                captions: list[str] = []
                for i, frame in enumerate(frames):
                    cap = caption_image(frame)
                    if cap:
                        captions.append(f"[{_timestamp(i, _FRAME_INTERVAL_SECONDS)}] {cap}")
                if captions:
                    parts.append("Escenas visuales:\n" + "\n".join(captions))

        return ExtractedDoc(text="\n\n".join(parts), page_map=[], extractor="video")

    def supported_extensions(self) -> list[str]:
        return self._EXTENSIONS
