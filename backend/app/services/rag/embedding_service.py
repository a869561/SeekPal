"""Embeddings locales con FastEmbed (ONNX Runtime).

Ejecuta el modelo directamente en proceso (sin HTTP). Providers en orden de
prioridad: CUDA (NVIDIA) > DirectML (AMD/Intel iGPU en Windows) > CPU.
El usuario instala el paquete de onnxruntime que corresponde a su hardware:
  - onnxruntime          → CPU pura (target principal)
  - onnxruntime-gpu      → NVIDIA CUDA
  - onnxruntime-directml → AMD/Intel iGPU en Windows

BGE-M3 puede producir NaN en ciertos textos. Estrategia recursiva: partir
el texto por la mitad hasta que funcione o sea demasiado corto.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import unicodedata
from pathlib import Path


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

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f�]")
_MIN_SPLIT_CHARS = 80


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
    """Embedding denso BGE-M3 (1024D) via FastEmbed ONNX."""

    def __init__(self, model: str, batch_size: int):
        import warnings
        # Intenta GPU (CUDA / DirectML); si falla, usa CPU
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                self._model = TextEmbedding(model_name=model, providers=_PROVIDERS)
            except Exception:
                self._model = TextEmbedding(model_name=model)
        self._batch_size = batch_size
        # Detectar provider activo para logging y system/info endpoint
        self.active_provider: str = "CPUExecutionProvider"
        try:
            session = getattr(self._model, "_model", None) or getattr(self._model, "model", None)
            if session is not None:
                inner = getattr(session, "_model", None) or getattr(session, "model", session)
                providers_list = inner.get_providers()
                if providers_list:
                    self.active_provider = providers_list[0]
        except Exception:
            pass
        _LABEL = {
            "CUDAExecutionProvider": "NVIDIA GPU (CUDA)",
            "DirectMLExecutionProvider": "AMD/Intel GPU (DirectML)",
            "CPUExecutionProvider": "CPU",
        }
        label = _LABEL.get(self.active_provider, self.active_provider)
        print(f"[seekpal] FastEmbed dense: {model} -> {label}")

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        return [e.tolist() for e in self._model.embed(texts, batch_size=self._batch_size)]

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        sanitized = [_sanitize(t) for t in texts]
        try:
            raw = await asyncio.to_thread(self._embed_sync, sanitized)
        except Exception:
            raw = [None] * len(sanitized)  # type: ignore[list-item]

        result: list[list[float] | None] = []
        for text, vec in zip(sanitized, raw):
            if vec is None:
                result.append(await self._embed_one_safe(text))
                continue
            if np.isnan(np.array(vec, dtype=np.float32)).any():
                result.append(await self._embed_one_safe(text))
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
        result = await self._embed_one_safe(_sanitize(text))
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
        print("[seekpal] FastEmbed sparse: Qdrant/bm25 cargado")

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
