"""Procesado de imagenes: OCR (rapidocr-onnxruntime) + captioning (Moondream via Ollama).

Combina dos pipelines complementarios:
  - OCR: extrae texto incrustado (screenshots, scans, pizarras con escritura).
  - Captioning: descripcion en lenguaje natural de la escena (gente, objetos,
    composicion). Usa Moondream2 servido por Ollama, reutilizando el cliente
    existente del LLM (sin torch ni transformers, solo HTTP a localhost:11434).

Ambas piezas son lazy: solo se cargan/usan cuando hay imagenes que indexar.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from ollama import AsyncClient

from app.services.rag._lazy import LazyService

logger = logging.getLogger("seekpal.image")

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR


_MOONDREAM_MODEL = os.getenv("SEEKPAL_VISION_MODEL", "moondream")
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_CAPTION_PROMPT = (
    "Describe esta imagen con un parrafo breve y concreto en espanol. "
    "Menciona los objetos principales, personas, texto visible, escenario "
    "y cualquier dato util para buscarla mas tarde."
)


def _load_ocr() -> "RapidOCR":
    from rapidocr_onnxruntime import RapidOCR
    logger.info("OCR: cargando RapidOCR (modelos PaddleOCR)...")
    instance = RapidOCR()
    logger.info("OCR: listo")
    return instance


def _load_caption_client() -> AsyncClient:
    return AsyncClient(host=_OLLAMA_URL, timeout=120.0)


_ocr = LazyService("OCR", _load_ocr)
_caption = LazyService("Captioning", _load_caption_client)


def ocr_image(path: Path) -> str:
    """Extrae texto de una imagen via OCR. Devuelve "" si no hay texto detectado."""
    engine = _ocr.get()
    if engine is None:
        return ""
    try:
        result, _ = engine(str(path))
        if not result:
            return ""
        # result = [(bbox, text, score), ...]
        return " ".join(item[1] for item in result if item and len(item) >= 2 and item[1])
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR fallo en %s: %s", path.name, exc)
        return ""


async def caption_image_async(path: Path) -> str:
    """Genera descripcion en lenguaje natural via Moondream/Ollama."""
    client = _caption.get()
    if client is None:
        return ""
    try:
        resp = await client.chat(
            model=_MOONDREAM_MODEL,
            messages=[{
                "role": "user",
                "content": _CAPTION_PROMPT,
                "images": [str(path)],
            }],
            options={"temperature": 0.2, "num_ctx": 2048},
        )
        return (resp.message.content or "").strip()
    except Exception as exc:  # noqa: BLE001
        # Si Ollama no tiene Moondream descargado, deshabilitar para esta sesion
        msg = str(exc).lower()
        model_missing = ("not found" in msg) or ("model" in msg and "pull" in msg)
        if model_missing:
            logger.warning(
                "Moondream no esta descargado en Ollama: 'ollama pull %s'", _MOONDREAM_MODEL
            )
            _caption.disable()
        else:
            logger.warning("Captioning fallo en %s: %s", path.name, exc)
        return ""


def caption_image(path: Path) -> str:
    """Wrapper sincrono para uso desde extractores sincronos."""
    try:
        return asyncio.run(caption_image_async(path))
    except RuntimeError:
        # Ya hay un event loop corriendo — usar otro thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, caption_image_async(path)).result()


def extract_image_text(path: Path) -> str:
    """Combina OCR + caption en un solo texto indexable."""
    caption = caption_image(path)
    ocr = ocr_image(path)
    parts: list[str] = []
    if caption:
        parts.append(f"Descripcion: {caption}")
    if ocr:
        parts.append(f"Texto en la imagen: {ocr}")
    return "\n\n".join(parts)
