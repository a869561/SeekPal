"""Procesado de imagenes: OCR (rapidocr-onnxruntime) + captioning (vision LLM via Ollama).

Combina dos pipelines complementarios:
  - OCR: extrae texto incrustado (screenshots, scans, pizarras con escritura).
  - Captioning: descripcion en lenguaje natural de la escena (gente, objetos,
    composicion). Usa un modelo de vision via Ollama (por defecto moondream;
    recomendado qwen2.5vl:3b para mayor calidad).

El captioning corre SIEMPRE en CPU (num_gpu=0) para evitar competencia de VRAM
con los modelos de embedding/OCR que ya usan la GPU durante la ingesta.
Configurable via SEEKPAL_VISION_MODEL (modelo) y SEEKPAL_VISION_NUM_GPU (gpu layers).

Ambas piezas son lazy: solo se cargan/usan cuando hay imagenes que indexar.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from ollama import AsyncClient, Client

from app.services.rag._lazy import LazyService

logger = logging.getLogger("seekpal.image")

if TYPE_CHECKING:
    from rapidocr_onnxruntime import RapidOCR


def _vision_num_gpu() -> int:
    """Devuelve num_gpu para el modelo de visión según el planificador.

    cuda → 99 (usa GPU), cpu → 0 (fuerza CPU).
    Fallback al env SEEKPAL_VISION_NUM_GPU si el planner no está disponible.
    """
    try:
        from app.services.rag.device_planner import get_device_for as _gdf
        return 99 if _gdf("vision") == "cuda" else 0
    except Exception:
        return int(os.getenv("SEEKPAL_VISION_NUM_GPU", "0"))


def _vision_model() -> str:
    """Devuelve el modelo de visión activo, resuelto en tiempo de llamada.

    Lee runtime_settings (que refleja el valor guardado en Mongo por el usuario)
    con fallback a la variable de entorno SEEKPAL_VISION_MODEL.
    El cambio entra en efecto tras reinicio (igual que el resto de settings RAG).
    """
    from app.core import runtime_settings  # import local para evitar ciclos en arranque
    return runtime_settings.get("visionModel") or os.getenv("SEEKPAL_VISION_MODEL", "moondream")
_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Prompt en prosa (sin listas numeradas) con instrucción anti-eco: los modelos
# pequeños (p.ej. moondream) tienden a repetir prompts estructurados en vez de
# describir. Validado empíricamente con qwen2.5vl:3b: produce captions ricos en
# español que nombran marcas/nombres propios sin repetir las instrucciones.
# Prompt deliberadamente CORTO: con qwen2.5vl:3b un prompt largo con muchas
# instrucciones (tipo, objetos, texto, marcas, términos de búsqueda…) hace que el
# modelo se atasque y genere muy lento (decenas de segundos) o derive a inglés. Un
# prompt breve produce la misma descripción útil en español en ~5 s. (Medido.)
_CAPTION_PROMPT = (
    "Describe en español, en 2 o 3 frases, lo que se ve en esta imagen: "
    "objetos, personas, texto o marcas visibles, y el escenario."
)
_CAPTION_PROMPT_RETRY = (
    "Describe esta imagen con detalle: colores, formas, objetos, "
    "personas, escenario y cualquier elemento visible. Siempre hay algo que describir, "
    "nunca dejes la respuesta vacia."
)
_CAPTION_PROMPT_FRAME = (
    "En una frase, describe brevemente lo que muestra este fotograma de vídeo."
)

# Marcadores de "ruido" entre signos que algunos VLM emiten como contenido al
# degenerar: ChatML ("<|im_start|>", qwen) o exclamaciones ("!!!IMAGE!!!",
# moondream). Es un patrón GENÉRICO (texto entre delimitadores), no una lista por
# modelo, para no tener que perseguir las manías de cada VLM nuevo.
_MARKER_RE = re.compile(r"<\|[^|]*\|>|!{2,}[^!]*!{2,}")
# Frase-preámbulo inicial que termina en ':' y salto de línea, que algunos modelos
# anteponen ("Aquí tienes una descripción:", "Sure, here's a description:"). Se
# reconoce el patrón (una línea corta inicial acabada en ':'), no el texto exacto.
_PREAMBLE_RE = re.compile(r"^[^\n:]{1,80}:\s*\n+")


def _sanitize_caption(text: str) -> str:
    """Normaliza y valida la salida del modelo de visión.

    Importante: la cura de fondo de la degeneración es el reescalado de la imagen
    (ver _image_bytes_for_ollama), no esto. Esta función es una RED DE SEGURIDAD
    genérica para poder cambiar de modelo de visión sin sorpresas: aplica reglas
    de normalización que NO dependen del modelo concreto —quitar marcadores entre
    delimitadores (ChatML de qwen, "!!!IMAGE!!!" de moondream) y una intro-preámbulo
    inicial acabada en ':' (gemma y otros)— y luego valida que quede una descripción
    real. Si no (vacío, solo símbolos, degenerado por repetición), devuelve "" para
    que actúe el retry / OCR / rescate por nombre en vez de indexar basura.
    """
    if not text:
        return ""
    cleaned = _MARKER_RE.sub(" ", text)
    cleaned = _PREAMBLE_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.split())
    # Puntuación/espacios sobrantes al principio (p. ej. tras quitar un marcador
    # quedaba ", a man…"). Regla genérica, no por modelo.
    cleaned = re.sub(r"^[\s,.;:–—-]+", "", cleaned)
    # ¿Queda texto real (alguna letra o dígito, no solo símbolos)?
    if not re.search(r"[^\W_]", cleaned):
        return ""
    words = cleaned.split()
    # Una descripción real es una frase de varias palabras. Rechazamos one-liners
    # degenerados como "!!!IMAGES!!!" o tokens sueltos (otra forma en que los VLM
    # pequeños "fallan" devolviendo un marcador en vez de describir).
    letter_words = [w for w in words if re.search(r"[^\W\d_]", w)]
    if len(letter_words) < 3:
        return ""
    # Degeneración por repetición: muchas palabras pero casi todas iguales.
    if len(words) >= 8 and len({w.lower() for w in words}) <= 2:
        return ""
    return cleaned


def _ensure_server_models() -> "tuple[Path, Path] | None":
    """Descarga los modelos server de PP-OCRv4 si no están en caché local.

    Busca el directorio de modelos del paquete OCR instalado y descarga
    los ficheros .onnx desde ModelScope si faltan. Devuelve (det, rec)
    o None si la descarga falla (el caller usará los modelos mobile).
    """
    import importlib.util
    import urllib.request

    for pkg in ("rapidocr_onnxruntime", "rapidocr"):
        spec = importlib.util.find_spec(pkg)
        if spec is not None and spec.origin is not None:
            models_dir = Path(spec.origin).parent / "models"
            break
    else:
        logger.warning("OCR server: paquete rapidocr no encontrado")
        return None

    models_dir.mkdir(exist_ok=True)

    _BASE = (
        "https://www.modelscope.cn/models/RapidAI/RapidOCR"
        "/resolve/master/onnx/PP-OCRv4"
    )
    _MODELS = [
        ("ch_PP-OCRv4_det_server.onnx", f"{_BASE}/det/ch_PP-OCRv4_det_server.onnx", "~47 MB"),
        ("ch_PP-OCRv4_rec_server.onnx", f"{_BASE}/rec/ch_PP-OCRv4_rec_server.onnx", "~90 MB"),
    ]

    result_paths: list[Path] = []
    for filename, url, size_hint in _MODELS:
        dest = models_dir / filename
        if dest.exists():
            logger.info("OCR server: %s ya en caché (%s)", filename, dest)
            result_paths.append(dest)
            continue

        logger.info("OCR server: descargando %s (%s) desde ModelScope...", filename, size_hint)
        try:
            urllib.request.urlretrieve(url, dest)
            size_mb = dest.stat().st_size / 1_000_000
            logger.info("OCR server: %s descargado (%.1f MB)", filename, size_mb)
            result_paths.append(dest)
        except Exception as exc:
            logger.warning("OCR server: descarga de %s fallida: %s — usando mobile", filename, exc)
            dest.unlink(missing_ok=True)
            return None

    return result_paths[0], result_paths[1]


def _ocr_providers() -> list[str]:
    """Devuelve la lista de providers ONNX para RapidOCR según el planificador.

    Si el planificador asigna "cuda" para el OCR se ofrecen también CUDAExecutionProvider
    y DirectMLExecutionProvider; si dice "cpu" solo se pasa CPUExecutionProvider.
    RapidOCR usa internamente onnxruntime y respeta la lista de providers igual que
    fastembed: toma el primero disponible y cae al siguiente si no está instalado.
    """
    from app.services.rag.device_planner import get_device_for
    ocr_device = get_device_for("ocr")
    if ocr_device == "cpu":
        return ["CPUExecutionProvider"]
    # "cuda": devolver la pila completa GPU → CPU para fallback automático.
    providers: list[str] = []
    try:
        import onnxruntime as _ort
        available = _ort.get_available_providers()
        for p in ("CUDAExecutionProvider", "DirectMLExecutionProvider", "CPUExecutionProvider"):
            if p in available:
                providers.append(p)
    except Exception:
        pass
    if not providers:
        providers = ["CPUExecutionProvider"]
    return providers


def _load_ocr() -> "RapidOCR":
    from app.core import runtime_settings
    from rapidocr_onnxruntime import RapidOCR
    quality = runtime_settings.get("ocrQuality", "mobile")
    providers = _ocr_providers()
    logger.info("OCR: cargando RapidOCR (calidad=%s, providers=%s)...", quality, providers)
    if quality == "server":
        paths = _ensure_server_models()
        if paths is not None:
            det_path, rec_path = paths
            try:
                instance = RapidOCR(
                    det_model_path=str(det_path),
                    rec_model_path=str(rec_path),
                )
                logger.info("OCR: modelos server cargados (PP-OCRv4 server, ~140 MB)")
            except Exception as exc:
                logger.warning("OCR server no disponible (%s) — usando mobile como fallback", exc)
                instance = RapidOCR()
        else:
            logger.warning("OCR server: descarga fallida — usando mobile como fallback")
            instance = RapidOCR()
    else:
        instance = RapidOCR()
    logger.info("OCR: listo")
    return instance


def _load_caption_client() -> Client:
    # Timeout de 30 s: suficiente para modelos de vision ligeros (moondream),
    # pero no tan alto como para bloquear la ingesta si Ollama no responde.
    # Cliente SINCRONO a proposito: caption_image se invoca desde threads worker
    # (asyncio.to_thread). Un AsyncClient se ata al event loop de su primer uso; al
    # llamarlo con asyncio.run() en cada imagen se creaba un loop nuevo y el cliente
    # cacheado quedaba atado a uno ya cerrado -> "Event loop is closed". httpx.Client
    # (que envuelve Client) es thread-safe, asi que un cliente compartido vale.
    return Client(host=_OLLAMA_URL, timeout=30.0)


_ocr = LazyService("OCR", _load_ocr)
_caption = LazyService("Captioning", _load_caption_client)
_caption_errors = 0  # errores de modelo/imagen (no conexion); >=5 desactiva
_caption_lock = threading.Semaphore(1)  # solo un captioning a la vez en Ollama
# El motor RapidOCR (sesión ONNX compartida) NO es seguro para llamadas
# concurrentes: durante la ingesta varias imágenes corren en paralelo y, sin
# serializar, todas menos una devolvían texto vacío (se perdía el OCR de, p. ej.,
# rangos.png). Un lock por inferencia lo resuelve; el OCR es rápido en CPU.
_ocr_lock = threading.Lock()

# Registrar modelos lazy para que get_model_status() los incluya
from app.services.rag._lazy import register as _register  # noqa: E402
_register(_ocr)
_register(_caption)


_FORMATS_NEEDING_CONVERSION = {".webp", ".avif", ".heic", ".heif"}

# Lado mayor máximo (px) al pasar imágenes al VLM. Las imágenes más grandes se
# reescalan: a resolución completa generan demasiados tokens de visión y el VLM
# pequeño degenera (ver _image_bytes_for_ollama).
_MAX_VISION_DIM = 1024


def _image_bytes_for_ollama(path: Path) -> bytes:
    """Devuelve los bytes de imagen listos para Ollama.

    Imágenes pequeñas en JPG/PNG se pasan tal cual. WEBP, AVIF y HEIC se
    convierten a PNG porque algunos modelos de visión en Ollama crashean
    ("model runner unexpectedly stopped") al recibir estos formatos.

    Además, las imágenes grandes se reescalan a _MAX_VISION_DIM px de lado mayor.
    Una captura 16:9 a resolución completa genera tantos *tokens* de visión que
    desbordan el contexto del VLM pequeño (qwen2.5vl:3b): el modelo degenera y
    emite sus tokens de plantilla ("<|im_start|>") en bucle en vez de describir,
    y además dispara la latencia en CPU (~400 s/imagen). Reescalar a ~1024 px
    elimina la degeneración y reduce la latencia varias veces, sin pérdida
    apreciable de detalle para el captioning.
    """
    needs_conversion = path.suffix.lower() in _FORMATS_NEEDING_CONVERSION
    try:
        import io
        from PIL import Image
        with Image.open(path) as img:
            too_big = max(img.size) > _MAX_VISION_DIM
            if not needs_conversion and not too_big:
                return path.read_bytes()
            rgb = img.convert("RGB")
            if too_big:
                rgb.thumbnail((_MAX_VISION_DIM, _MAX_VISION_DIM))
            buf = io.BytesIO()
            rgb.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return path.read_bytes()


def warm_ocr() -> None:
    """Carga anticipada del motor OCR.

    La carga en frío (modelos server ~140 MB la primera vez) puede superar el
    timeout de 30 s que extract_image_text_async aplica al OCR de cada imagen.
    Llamar a esto antes de la fase de imágenes mueve ese coste fuera del timeout
    por imagen, evitando que las primeras imágenes pierdan el OCR. Idempotente."""
    _ocr.get()


def ocr_image(path: Path) -> str:
    """Extrae texto de una imagen via OCR. Devuelve "" si no hay texto detectado.

    Carga la imagen via Pillow en lugar de pasar la ruta directamente: evita que
    cv2.imread() falle silenciosamente con WEBP u otros formatos no soportados
    por la build de OpenCV del entorno.
    """
    engine = _ocr.get()
    if engine is None:
        return ""
    try:
        import numpy as np
        from PIL import Image
        img = np.array(Image.open(path).convert("RGB"))
        with _ocr_lock:  # serializa: RapidOCR no es seguro en concurrencia
            result, _ = engine(img)
        if not result:
            return ""
        return " ".join(item[1] for item in result if item and len(item) >= 2 and item[1])
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR fallo en %s: %s", path.name, exc)
        return ""


def caption_image(path: Path, brief: bool = False) -> str:
    """Genera descripcion en lenguaje natural via Moondream/Ollama.

    Sincrono: se invoca desde extractores que corren en threads worker. Usa el
    Client sincrono de ollama para evitar el "Event loop is closed" que daba el
    AsyncClient cacheado entre loops creados por asyncio.run().

    brief=True: usa un prompt corto de una frase y num_predict=96. Pensado
    para frames de vídeo (numerosos) donde la cota baja de generación reduce
    el coste total sin perder la señal principal del fotograma.
    brief=False (defecto): prompt rico acotado a 220 tokens de salida.

    Politica de fallos:
    - Ollama ocupado/timeout (fallo TEMPORAL): se omite esta imagen sin
      deshabilitar. La siguiente imagen lo intentara igualmente — el timeout
      de 30s ya limita el coste por imagen.
    - Modelo no instalado (fallo PERMANENTE): se desactiva inmediatamente para
      toda la sesion (el modelo no va a aparecer solo).
    - Error de modelo/imagen (fallo de CONTENIDO): se desactiva tras 5 consecutivos.
    """
    global _caption_errors
    client = _caption.get()
    if client is None:
        return ""
    prompt = _CAPTION_PROMPT_FRAME if brief else _CAPTION_PROMPT
    num_predict = 96 if brief else 220
    model = _vision_model()
    with _caption_lock:
        try:
            resp = client.chat(
                model=model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [_image_bytes_for_ollama(path)],
                }],
                options={"temperature": 0.2, "num_ctx": 2048, "num_gpu": _vision_num_gpu(), "num_predict": num_predict},
            )
            _caption_errors = 0
            return _sanitize_caption(resp.message.content or "")
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()

            model_missing = ("not found" in msg) or ("model" in msg and "pull" in msg)
            ollama_unavailable = (
                "connect" in msg
                or "refused" in msg
                or "unreachable" in msg
                or "timeout" in msg
                or "timed out" in msg
                or "failed to connect" in msg
            )

            if model_missing:
                logger.warning(
                    "Modelo '%s' no descargado en Ollama ('ollama pull %s'). "
                    "Captioning desactivado para esta sesion.",
                    model, model,
                )
                _caption.disable()
                _caption_errors = 0
            elif ollama_unavailable:
                logger.debug("Captioning: Ollama ocupado/timeout para %s, se omite.", path.name)
            else:
                _caption_errors += 1
                if _caption_errors >= 5:
                    logger.warning(
                        "Captioning: 5 errores consecutivos de modelo/imagen. "
                        "Desactivado para esta sesion."
                    )
                    _caption.disable()
                    _caption_errors = 0
                else:
                    logger.warning("Captioning fallo en %s: %s", path.name, exc)
            return ""


async def flush_llm_for_captioning() -> None:
    """Descarga el modelo LLM de VRAM antes de la fase de captioning.

    Ollama solo puede tener un modelo cargado a la vez. Si el LLM estaba
    activo, esta llamada con keep_alive=0 lo descarga inmediatamente para
    que moondream pueda cargar sin necesidad de swap durante la ingesta.
    Fallo silencioso: si Ollama no responde o el modelo ya estaba descargado,
    el captioning lo intentará igualmente.
    """
    from app.core.config import settings
    try:
        client = AsyncClient(host=_OLLAMA_URL, timeout=10.0)
        await client.generate(model=settings.llm_model, prompt="", keep_alive=0)
        logger.debug("flush_llm_for_captioning: '%s' descargado de VRAM", settings.llm_model)
    except Exception:
        pass  # No crítico: el captioning reintentará igualmente


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


# ---------------------------------------------------------------------------
# Versión async (usada por index_service.prepare_file para imágenes)
# ---------------------------------------------------------------------------

# asyncio.Semaphore para limitar a 1 caption concurrente — igual que
# _caption_lock, pero genuinamente cancelable: cuando asyncio.wait_for
# dispara, el semáforo se libera de inmediato sin dejar threads zombi.
_async_caption_sem = asyncio.Semaphore(1)


async def caption_image_async(path: Path, retry: bool = False) -> str:
    """Caption con AsyncClient + asyncio.Semaphore — cancelable por asyncio.

    A diferencia de caption_image (sync + threading.Semaphore), esta versión
    puede ser cancelada por asyncio.wait_for sin dejar threads bloqueados en
    el semáforo, eliminando los timeouts en cascada entre imágenes del mismo
    grupo de ingesta.
    retry=True usa un prompt más corto y directo para imágenes donde el modelo
    devolvió vacío en el primer intento.
    """
    global _caption_errors
    if _caption.disabled:
        return ""

    prompt = _CAPTION_PROMPT_RETRY if retry else _CAPTION_PROMPT

    model = _vision_model()
    async with _async_caption_sem:
        try:
            client = AsyncClient(host=_OLLAMA_URL, timeout=150.0)
            resp = await client.chat(
                model=model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [_image_bytes_for_ollama(path)],
                }],
                options={"temperature": 0.2, "num_ctx": 2048, "num_gpu": _vision_num_gpu(), "num_predict": 220},
            )
            _caption_errors = 0
            return _sanitize_caption(resp.message.content or "")
        except asyncio.CancelledError:
            raise  # propagar: el semáforo ya se liberó en __aexit__
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).lower()
            model_missing = ("not found" in msg) or ("model" in msg and "pull" in msg)
            ollama_unavailable = (
                "connect" in msg or "refused" in msg or "unreachable" in msg
                or "timeout" in msg or "timed out" in msg or "failed to connect" in msg
            )
            if model_missing:
                logger.warning(
                    "Modelo '%s' no descargado en Ollama ('ollama pull %s'). "
                    "Captioning desactivado para esta sesion.",
                    model, model,
                )
                _caption.disable()
                _caption_errors = 0
            elif ollama_unavailable:
                logger.debug("Captioning: Ollama ocupado/timeout para %s, se omite.", path.name)
            else:
                _caption_errors += 1
                if _caption_errors >= 5:
                    logger.warning(
                        "Captioning: 5 errores consecutivos. Desactivado para esta sesion."
                    )
                    _caption.disable()
                    _caption_errors = 0
                else:
                    logger.warning("Captioning fallo en %s: %s", path.name, exc)
            return ""


async def extract_image_text_async(path: Path) -> str:
    """OCR + captioning en paralelo con timeouts independientes.

    OCR (CPU, sin red) y captioning (Ollama async) corren simultáneamente.
    Si captioning tarda demasiado o falla, OCR ya tiene resultado → el fichero
    nunca se marca como error solo por lentitud del modelo de visión.

    Timeouts:
      - OCR: 120s. El OCR está serializado (_ocr_lock), así que este margen
        cubre tanto la inferencia (rápida en CPU) como la cola de imágenes
        concurrentes esperando el lock; con 30s las últimas de un lote grande
        agotaban el tiempo esperando turno y perdían el OCR.
      - Caption: el AsyncClient ya tiene timeout=150s para la llamada a Ollama.
        No se envuelve caption_image_async con wait_for porque el semáforo puede
        esperar legítimamente mientras otra imagen está siendo captionada — ese
        tiempo de cola no es un cuelgue. El timeout del cliente cubre inferencia
        atascada.
    """
    async def _ocr_task() -> str:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(ocr_image, path), timeout=120.0,
            )
        except Exception:  # noqa: BLE001
            return ""

    async def _caption_task() -> str:
        try:
            result = await caption_image_async(path)
            if result:
                return result
            # Retry con prompt más directo si el modelo devolvió vacío
            return await caption_image_async(path, retry=True)
        except Exception:  # noqa: BLE001
            return ""

    ocr, caption = await asyncio.gather(_ocr_task(), _caption_task())

    parts: list[str] = []
    if caption:
        parts.append(f"Descripcion: {caption}")
    if ocr:
        parts.append(f"Texto en la imagen: {ocr}")
    return "\n\n".join(parts)
