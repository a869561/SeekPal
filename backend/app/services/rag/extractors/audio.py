"""Extractor de audio: transcribe la pista hablada con faster-whisper."""

from __future__ import annotations

import logging
from pathlib import Path

from app.services.rag.audio_service import transcribe
from app.services.rag.extractors.base import BaseExtractor
from app.services.rag.types import ExtractedDoc

logger = logging.getLogger("seekpal.audio")


class AudioExtractor(BaseExtractor):
    _EXTENSIONS = [
        ".mp3", ".m4a", ".wav", ".ogg", ".oga", ".flac",
        ".aac", ".wma", ".opus", ".aiff",
    ]

    def extract(self, path: Path) -> ExtractedDoc:
        try:
            text = transcribe(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Audio %s: transcripcion fallida (%s) — omitido", path.name, exc)
            text = ""
        return ExtractedDoc(text=text, page_map=[], extractor="audio")

    def supported_extensions(self) -> list[str]:
        return self._EXTENSIONS
