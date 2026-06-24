"""Embeddings locales con FastEmbed (ONNX Runtime).

Ejecuta el modelo directamente en proceso (sin HTTP). Providers en orden de
prioridad: CUDA (NVIDIA) > DirectML (AMD/Intel iGPU en Windows) > CPU.
El usuario instala el paquete de onnxruntime que corresponde a su hardware:
  - onnxruntime          → CPU pura (target principal)
  - onnxruntime-gpu      → NVIDIA CUDA
  - onnxruntime-directml → AMD/Intel iGPU en Windows

multilingual-e5-large puede producir NaN en ciertos textos (quirk observado
también en modelos anteriores; se conserva la estrategia recursiva como defensa
genérica): partir el texto por la mitad hasta que funcione o sea demasiado corto.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path

logger = logging.getLogger("seekpal.embedding")


def _setup_cuda_pip_dlls() -> None:
    """Anade al DLL search path los binarios de los paquetes pip nvidia-*.

    Permite que ONNX Runtime cargue cublasLt64_12.dll, cudnn64_9.dll, etc.
    desde wheels (nvidia-cublas-cu12, nvidia-cudnn-cu12, ...) sin necesidad
    de tener CUDA Toolkit instalado a nivel de sistema.

    Hace dos cosas porque add_dll_directory solo afecta a DLLs cargadas por
    Python (no a dependencias transitivas que carga el codigo C++ de ONNX):
      1. os.add_dll_directory(...)  -> para DLLs que Python carga directamente
      2. prepend a $env:PATH         -> para que el loader de Windows resuelva
                                        dependencias transitivas (cublas64_12,
                                        cufft64_11, etc.) al cargar
                                        onnxruntime_providers_cuda.dll

    Debe ejecutarse ANTES de importar fastembed/onnxruntime.
    """
    if os.name != "nt":
        return
    try:
        nvdir = Path(sys.executable).parent.parent / "Lib" / "site-packages" / "nvidia"
        if not nvdir.exists():
            return
        bin_dirs: list[str] = []
        for sub in nvdir.iterdir():
            bin_dir = sub / "bin"
            if bin_dir.exists():
                bin_dirs.append(str(bin_dir))
                try:
                    os.add_dll_directory(str(bin_dir))
                except (OSError, FileNotFoundError):
                    pass
        if bin_dirs:
            os.environ["PATH"] = os.pathsep.join(bin_dirs) + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


_setup_cuda_pip_dlls()

import numpy as np  # noqa: E402
from fastembed import SparseTextEmbedding, TextEmbedding  # noqa: E402
from qdrant_client.http.models import SparseVector  # noqa: E402

# Suprimir warnings informativos de ORT sobre asignación de nodos a providers.
# ORT asigna intencionalmente ops de shape a CPU aunque el provider preferido sea
# CUDA — es optimización deliberada, no un problema. Nivel 3 = solo errores reales.
try:
    import onnxruntime as _ort
    _ort.set_default_logger_severity(3)
except Exception:
    pass

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f�]")
_MIN_SPLIT_CHARS = 80

# Prefijos requeridos por intfloat/multilingual-e5-large (y familia e5 en general).
# El modelo fue entrenado con "query: " / "passage: " antepuestos; sin ellos el input
# está fuera de distribución y el recall denso se degrada, sobre todo cross-lingual.
_E5_QUERY_PREFIX   = "query: "
_E5_PASSAGE_PREFIX = "passage: "


def _detect_active_provider(model_obj: object) -> str:
    """Inspecciona el modelo FastEmbed para detectar que ONNX provider esta usando.

    FastEmbed envuelve InferenceSession en varias capas (TextEmbedding ->
    OnnxTextEmbedding -> InferenceSession, TextCrossEncoder ->
    OnnxTextCrossEncoder -> InferenceSession). Busca recursivamente hasta
    encontrar un objeto con get_providers().
    """
    visited: set[int] = set()
    candidates = [model_obj]
    while candidates:
        obj = candidates.pop(0)
        if id(obj) in visited:
            continue
        visited.add(id(obj))
        if hasattr(obj, "get_providers"):
            try:
                providers = obj.get_providers()
                if providers:
                    return providers[0]
            except Exception:
                pass
        # Buscar atributos comunes de wrapping en FastEmbed
        for attr in ("model", "_model", "session", "_session", "ort_session"):
            inner = getattr(obj, attr, None)
            if inner is not None and id(inner) not in visited:
                candidates.append(inner)
    return "CPUExecutionProvider"


def _cuda_runtime_available() -> bool:
    """True si las DLLs de CUDA 12 runtime estan cargables (system o pip).

    Despues de _setup_cuda_pip_dlls() esta comprobacion encuentra tambien las
    DLLs que vienen de los paquetes pip nvidia-* (no solo del CUDA Toolkit).
    """
    if os.name != "nt":
        return True  # Linux/Mac: confiar en LD_LIBRARY_PATH
    import ctypes
    try:
        ctypes.WinDLL("cublasLt64_12.dll")
        return True
    except (OSError, AttributeError):
        return False


# Providers en orden de prioridad: GPU NVIDIA > GPU AMD/Intel (DirectML) > CPU.
# CUDA solo se ofrece si las DLLs estan disponibles para evitar errores
# ruidosos de ONNX Runtime cuando onnxruntime-gpu esta instalado sin CUDA Toolkit.
_PROVIDERS: list[str] = []
if _cuda_runtime_available():
    _PROVIDERS.append("CUDAExecutionProvider")
_PROVIDERS.extend(["DirectMLExecutionProvider", "CPUExecutionProvider"])


def _sanitize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _CTRL.sub(" ", text)
    return " ".join(text.split())


class EmbeddingService:
    """Embedding denso multilingual-e5-large (1024D) via FastEmbed ONNX."""

    def __init__(self, model: str, batch_size: int):
        import warnings
        from app.services.rag.device_planner import get_device_for

        # El planificador decide si los embeddings van a GPU o CPU.
        # En el preset "search" (default) se fuerzan a CPU para dejar la VRAM
        # al LLM de Ollama; en "ingest" se mandan a GPU para mayor velocidad.
        emb_device = get_device_for("embeddings")
        providers = ["CPUExecutionProvider"] if emb_device == "cpu" else _PROVIDERS

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self._model = TextEmbedding(model_name=model, providers=providers)
            except Exception:
                # Fallback a CPU si el provider preferido falla (GPU no disponible, etc.)
                self._model = TextEmbedding(model_name=model)
        self._batch_size = batch_size
        # Activar prefijos e5 si el modelo es de la familia e5 (intfloat/multilingual-e5-*,
        # intfloat/e5-*, etc.). Guard: si se cambia a bge-m3 u otro modelo sin prefijos,
        # self._e5 será False y los prefijos no se aplicarán.
        self._e5: bool = "e5" in model.lower()
        # Detectar provider activo para logging y system/info endpoint
        self.active_provider = _detect_active_provider(self._model)
        _LABEL = {
            "CUDAExecutionProvider": "NVIDIA GPU (CUDA)",
            "DirectMLExecutionProvider": "AMD/Intel GPU (DirectML)",
            "CPUExecutionProvider": "CPU",
        }
        label = _LABEL.get(self.active_provider, self.active_provider)
        logger.info("FastEmbed dense: %s -> %s", model, label)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        return [e.tolist() for e in self._model.embed(texts, batch_size=self._batch_size)]

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        sanitized = [_sanitize(t) for t in texts]
        # Para modelos e5, anteponer el prefijo "passage: " a cada texto saneado.
        # El prefijo va SOLO al embedding denso; el texto original (sanitized) se
        # preserva para el fallback por-texto de forma que el manejo de NaN siga
        # operando sobre el texto con prefijo (igual que en el batch principal).
        to_embed = [_E5_PASSAGE_PREFIX + t for t in sanitized] if self._e5 else sanitized
        try:
            raw = await asyncio.to_thread(self._embed_sync, to_embed)
        except Exception:
            raw = [None] * len(sanitized)  # type: ignore[list-item]

        result: list[list[float] | None] = []
        for prefixed, vec in zip(to_embed, raw):
            if vec is None:
                result.append(await self._embed_one_safe(prefixed))
                continue
            if np.isnan(np.array(vec, dtype=np.float32)).any():
                result.append(await self._embed_one_safe(prefixed))
            else:
                result.append(vec)
        return result

    async def _embed_one_safe(self, text: str) -> list[float] | None:
        """Embed un texto con división recursiva si produce NaN."""
        if not text.strip():
            return None
        try:
            vecs = await asyncio.to_thread(self._embed_sync, [text])
            arr = np.array(vecs[0], dtype=np.float32)
            if np.isnan(arr).any():
                raise ValueError("NaN")
            return vecs[0]
        except Exception:
            if len(text) < _MIN_SPLIT_CHARS:
                return None
            mid = len(text) // 2
            split = text.rfind(" ", _MIN_SPLIT_CHARS // 2, mid)
            if split == -1:
                split = mid
            left = await self._embed_one_safe(text[:split])
            right = await self._embed_one_safe(text[split:])
            if left is not None and right is not None:
                return [(a + b) / 2 for a, b in zip(left, right)]
            return left or right

    async def embed_query(self, text: str) -> list[float]:
        sanitized = _sanitize(text)
        # Para modelos e5, anteponer "query: " antes de embeddear la consulta.
        to_embed = (_E5_QUERY_PREFIX + sanitized) if self._e5 else sanitized
        result = await self._embed_one_safe(to_embed)
        if result is None:
            raise RuntimeError(f"Cannot embed query (too short or NaN): {text[:60]!r}")
        return result


class SparseEmbeddingService:
    """Embedding sparse BM25 via FastEmbed (Qdrant/bm25).

    Produce vectores sparse IDF-ponderados compatibles con el campo 'bm25' de
    la colección Qdrant. No usa GPU — es pura tokenización + TF/IDF, muy rápido.
    """

    def __init__(self) -> None:
        self._model = SparseTextEmbedding(model_name="Qdrant/bm25")
        logger.info("FastEmbed sparse: Qdrant/bm25 cargado")

    def _embed_sync(self, texts: list[str]) -> list[SparseVector]:
        return [
            SparseVector(indices=list(map(int, e.indices)), values=list(map(float, e.values)))
            for e in self._model.embed(texts)
        ]

    async def embed_texts(self, texts: list[str]) -> list[SparseVector]:
        if not texts:
            return []
        return await asyncio.to_thread(self._embed_sync, texts)

    async def embed_query(self, text: str) -> SparseVector:
        results = await asyncio.to_thread(self._embed_sync, [_sanitize(text)])
        return results[0]


class RerankerService:
    """Cross-encoder reranker via FastEmbed (jinaai/jina-reranker-v2-base-multilingual por defecto).

    Se usa despues del retrieval inicial: el hybrid search devuelve top_k * N
    candidatos, el reranker los reordena con un cross-encoder mas preciso y
    nos quedamos con los top_k mejores. +5-10pp recall@k segun el informe.

    Usa los mismos providers ONNX (CUDA/DirectML/CPU) que TextEmbedding.
    El modelo se carga en __init__ — coste fijo de arranque ~1s en GPU, ~3s
    en CPU. Tamano: jinaai/jina-reranker-v2-base-multilingual ~570 MB.
    """

    def __init__(self, model: str, device: str = "auto") -> None:
        import warnings
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
        except ImportError:
            try:
                from fastembed import TextCrossEncoder  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    f"FastEmbed no expone TextCrossEncoder en esta version: {exc}"
                ) from exc
        # El planificador de dispositivos decide si el reranker va a GPU o CPU.
        # Si el caller pasa un device explícito ("cpu"/"cuda"/"auto"), se usa ese;
        # si es "auto" (default), se consulta al planificador.
        # En preset "search" el reranker es candidato a GPU (fase query, alta prioridad);
        # en hardware de 4 GB normalmente no cabe junto al LLM, así que el planner
        # lo mandará a CPU de todas formas.
        from app.services.rag.device_planner import get_device_for
        resolved_device = device if device != "auto" else get_device_for("reranker")
        providers = ["CPUExecutionProvider"] if resolved_device == "cpu" else _PROVIDERS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self._model = TextCrossEncoder(model_name=model, providers=providers)
            except Exception:
                self._model = TextCrossEncoder(model_name=model)
        self._model_name = model
        self.active_provider = _detect_active_provider(self._model)
        label = {
            "CUDAExecutionProvider": "NVIDIA GPU (CUDA)",
            "DirectMLExecutionProvider": "AMD/Intel GPU (DirectML)",
            "CPUExecutionProvider": "CPU",
        }.get(self.active_provider, self.active_provider)
        logger.info("FastEmbed reranker: %s -> %s", model, label)

    # Pasajes por forward del cross-encoder. El batch interno de FastEmbed (64)
    # dispara buffers de atencion de 3-4 GB y revienta GPUs de 4 GB (GTX 1650);
    # 8 acota el pico a ~150-200 MB. Los scores son por par (query, pasaje),
    # asi que trocear externamente no altera el resultado.
    _RERANK_BATCH = 8

    # Caracteres maximos de cada pasaje SOLO para puntuar (el texto completo
    # sigue intacto para snippets y para el LLM). El coste del cross-encoder
    # es ~lineal en tokens. Con chunks de 512 tokens (~2300 chars) hay que ser
    # conservador: 1200 cortaba la senal de relevancia de chunks cuya mencion
    # clave caia tarde ('propuesta TFG' pasaba de -0.04 a <-1.1 y se podaba);
    # 2000 conserva ~85% del chunk y solo recorta colas anomalas.
    _RERANK_MAX_CHARS = 2000

    def _rerank_sync(self, query: str, passages: list[str]) -> list[float]:
        # TextCrossEncoder.rerank devuelve un generador de floats en el mismo orden
        truncated = [p[: self._RERANK_MAX_CHARS] for p in passages]
        scores: list[float] = []
        for i in range(0, len(truncated), self._RERANK_BATCH):
            batch = truncated[i : i + self._RERANK_BATCH]
            scores.extend(float(s) for s in self._model.rerank(query, batch))
        return scores

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return await asyncio.to_thread(self._rerank_sync, _sanitize(query), passages)
