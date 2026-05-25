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
import os
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from ollama import AsyncClient

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR


_MOONDREAM_MODEL = os.getenv("SEEKPAL_VISION_MODEL", "moondream")
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_CAPTION_PROMPT = (
    "Describe esta imagen con un parrafo breve y concreto en espanol. "
    "Menciona los objetos principales, personas, texto visible, escenario "
    "y cualquier dato util para buscarla mas tarde."
)

_ocr: "RapidOCR | None" = None
_ocr_lock = Lock()
_ocr_disabled = False

_caption_client: AsyncClient | None = None
_caption_lock = Lock()
_caption_disabled = False


def _get_ocr() -> "RapidOCR | None":
    global _ocr, _ocr_disabled
    if _ocr_disabled:
        return None
    if _ocr is not None:
        return _ocr
    with _ocr_lock:
        if _ocr is not None:
            return _ocr
        try:
            from rapidocr_onnxruntime import RapidOCR
            print("[seekpal] OCR: cargando RapidOCR (modelos PaddleOCR)...")
            _ocr = RapidOCR()
            print("[seekpal] OCR: listo")
        except Exception as exc:  # noqa: BLE001
            print(f"[seekpal] OCR: error al inicializar — {exc}")
            _ocr_disabled = True
            return None
    return _ocr


def _get_caption_client() -> AsyncClient | None:
    global _caption_client, _caption_disabled
    if _caption_disabled:
        return None
    if _caption_client is not None:
        return _caption_client
    with _caption_lock:
        if _caption_client is not None:
            return _caption_client
        try:
            _caption_client = AsyncClient(host=_OLLAMA_URL, timeout=120.0)
        except Exception as exc:  # noqa: BLE001
            print(f"[seekpal] Captioning: error creando cliente Ollama — {exc}")
            _caption_disabled = True
            return None
    return _caption_client


def ocr_image(path: Path) -> str:
    """Extrae texto de una imagen via OCR. Devuelve "" si no hay texto detectado."""
    engine = _get_ocr()
    if engine is None:
        return ""
    try:
        result, _ = engine(str(path))
        if not result:
            return ""
        # result = [(bbox, text, score), ...]
        return " ".join(item[1] for item in result if item and len(item) >= 2 and item[1])
    except Exception as exc:  # noqa: BLE001
        print(f"[seekpal] OCR fallo en {path.name}: {exc}")
        return ""


async def caption_image_async(path: Path) -> str:
    """Genera descripcion en lenguaje natural via Moondream/Ollama."""
    global _caption_disabled
    client = _get_caption_client()
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
        if "not found" in msg or "model" in msg and "pull" in msg:
            print(f"[seekpal] Moondream no esta descargado en Ollama: 'ollama pull {_MOONDREAM_MODEL}'")
            _caption_disabled = True
        else:
            print(f"[seekpal] Captioning fallo en {path.name}: {exc}")
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
