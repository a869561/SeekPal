"""Transcripcion de audio con faster-whisper (CTranslate2, INT8).

Singleton lazy: el modelo solo se carga la primera vez que se transcribe
un fichero. Detecta automaticamente GPU (CUDA) si las wheels nvidia-* +
onnxruntime-gpu estan presentes; cae a CPU INT8 en otro caso.

Perfil del informe v3: faster-whisper "small" por defecto (~244 MB, WER
3-6 % en espanol). Se puede subir a "medium" via env var.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from app.core import runtime_settings
from app.services.rag._lazy import LazyService

logger = logging.getLogger("seekpal.audio")

if TYPE_CHECKING:
    from faster_whisper import WhisperModel


# Defaults if runtime_settings hasn't been loaded yet (e.g. tests).
# El env var SEEKPAL_WHISPER_MODEL sigue funcionando como override.
_DEFAULT_LANG = os.getenv("SEEKPAL_WHISPER_LANG", "auto")  # auto = detect


def _detect_device() -> tuple[str, str]:
    """Decide device + compute_type segun hardware disponible.

    Devuelve (device, compute_type):
      - ("cuda", "int8_float16") si CUDA esta listo (wheels nvidia-* cargables)
      - ("cpu",  "int8")          fallback siempre
    """
    if os.name == "nt":
        try:
            import ctypes
            ctypes.WinDLL("cublasLt64_12.dll")
            return ("cuda", "int8_float16")
        except (OSError, AttributeError):
            pass
    elif os.name == "posix":
        try:
            import ctypes.util
            if ctypes.util.find_library("cublasLt"):
                return ("cuda", "int8_float16")
        except Exception:
            pass
    return ("cpu", "int8")


def _load_whisper() -> "WhisperModel":
    from faster_whisper import WhisperModel
    model_name = os.getenv("SEEKPAL_WHISPER_MODEL") or runtime_settings.get(
        "whisperModel", "small"
    )
    device, compute_type = _detect_device()
    logger.info("Whisper: cargando '%s' en %s (%s)...", model_name, device, compute_type)
    instance = WhisperModel(model_name, device=device, compute_type=compute_type)
    logger.info("Whisper: listo")
    return instance


_whisper = LazyService("Whisper", _load_whisper)


def get_whisper() -> "WhisperModel | None":
    """Devuelve el modelo Whisper (carga lazy). None si falla la inicializacion.

    El nombre del modelo se lee de runtime_settings (override env:
    SEEKPAL_WHISPER_MODEL). Valores validos: tiny | base | small | medium | large.
    """
    return _whisper.get()


def transcribe(path: Path) -> str:
    """Transcribe un fichero de audio. Devuelve "" si Whisper no esta disponible."""
    model = get_whisper()
    if model is None:
        return ""
    lang = None if _DEFAULT_LANG == "auto" else _DEFAULT_LANG
    segments, _info = model.transcribe(str(path), language=lang, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments if seg.text)
