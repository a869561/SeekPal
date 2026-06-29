"""Ajustes en memoria leidos de Mongo al iniciar el backend.

Cubre los flags que afectan a servicios cargados una sola vez por sesion
(reranker, Whisper) y otros que se consultan por operacion (intervalos de
muestreo de video, master switch de multimedia).

Flujo:
  1. connect_database() llama a load_runtime_settings(config_settings) tras
     init_beanie.
  2. Los servicios consultan get('clave', default) en lugar de leer Mongo
     directamente (mantiene los servicios desacoplados del modelo).
  3. Cuando el usuario cambia ajustes desde la UI, se guarda en Mongo y se
     reinicia el backend (exit 99 + uvicorn loop) — los servicios releen
     los nuevos valores al volver a arrancar.
"""

from __future__ import annotations

import os
from typing import Any


# Valores por defecto si Mongo no esta disponible o el campo no existe.
# Mantenerlos sincronizados con UserSettings de app/models/config.py.
_defaults: dict[str, Any] = {
    "rerankerEnabled": True,
    "whisperModel": "small",
    "llmModel": os.getenv("LLM_MODEL", "gemma3:4b"),
    "useDocling": False,
    "indexMultimedia": True,
    "videoFrameInterval": 30,
    "videoMaxFrames": 20,
    "ocrQuality": "mobile",
    "visionModel": os.getenv("SEEKPAL_VISION_MODEL", "qwen2.5vl:3b"),
    "autoFreePreviousVisionModel": False,
    # Planificador de dispositivos VRAM-aware.
    # "search" (default): prioriza latencia de consulta (reranker en GPU).
    # "ingest": prioriza velocidad de ingesta (embeddings/Whisper/OCR en GPU).
    "processingPriority": "search",
    # Overrides manuales por componente. {} = todo en auto (el planner decide).
    "deviceOverrides": {},
}

_settings: dict[str, Any] = dict(_defaults)


def load_runtime_settings(user_settings: object) -> None:
    """Carga los campos relevantes desde el objeto UserSettings de Mongo."""
    for key in _defaults:
        value = getattr(user_settings, key, None)
        if value is not None:
            _settings[key] = value


def get(key: str, default: Any | None = None) -> Any:
    """Lee un ajuste runtime. Si la clave no existe, devuelve `default` o el
    default global."""
    if key in _settings:
        return _settings[key]
    if default is not None:
        return default
    return _defaults.get(key)


def all_settings() -> dict[str, Any]:
    """Snapshot de todos los ajustes runtime (para debugging / endpoints)."""
    return dict(_settings)
