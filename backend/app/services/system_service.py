"""Servicios del sistema: selector de carpeta nativo, información de hardware y
gestión de aceleración GPU (instalación automática de onnxruntime y reinicio).

El diálogo de selección de carpeta se ejecuta en un subproceso Python con
tkinter para ser multiplataforma y no bloquear el event loop de FastAPI.
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Literal

import psutil

# Archivo de preferencia del provider IA (leido por start.bat y backend).
# Valores: "auto" | "cpu" | "cuda" | "directml". "auto" = autodetectar hardware.
# Vive en backend/ junto a los flags .models_*. Path se resuelve relativo al
# fichero (app/services/system_service.py → backend/ es 3 niveles arriba).
_PROVIDER_PREF_FILE = Path(__file__).resolve().parents[2] / ".provider_preference"
_VALID_PREFS = {"auto", "cpu", "cuda", "directml"}

# Tiempo entre devolver la respuesta HTTP y exit(99). 0.3s era ajustado: en
# redes lentas el cliente perdia la respuesta. 1.5s da margen para que uvicorn
# termine de enviar el body y el frontend reciba {"status":"restarting"}.
_RESTART_DELAY_S = 1.5


def get_provider_preference() -> str:
    """Lee la preferencia guardada. Devuelve 'auto' si no existe o es invalida."""
    try:
        value = _PROVIDER_PREF_FILE.read_text(encoding="utf-8").strip().lower()
        return value if value in _VALID_PREFS else "auto"
    except (OSError, FileNotFoundError):
        return "auto"


def save_provider_preference(pref: str) -> None:
    """Guarda la preferencia. start.bat la lee en el siguiente arranque."""
    if pref not in _VALID_PREFS:
        raise ValueError(f"Preferencia invalida: {pref}")
    try:
        _PROVIDER_PREF_FILE.write_text(pref, encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Selector de carpeta (ya existente)
# ---------------------------------------------------------------------------

_PICKER_CODE = (
    "import tkinter as tk\n"
    "from tkinter import filedialog\n"
    "root = tk.Tk()\n"
    "root.withdraw()\n"
    "root.attributes('-topmost', True)\n"
    "path = filedialog.askdirectory(title='Seleccionar directorio para SeekPal')\n"
    "print(path)\n"
)


def _run_picker(timeout: float) -> str:
    try:
        result = subprocess.run(
            [sys.executable, "-c", _PICKER_CODE],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ""
    return result.stdout.strip()


async def pick_folder(timeout: float = 120.0) -> str:
    return await asyncio.to_thread(_run_picker, timeout)


# ---------------------------------------------------------------------------
# Detección de hardware
# ---------------------------------------------------------------------------

def _detect_gpus_sync() -> list[str]:
    """Detecta tarjetas gráficas vía WMI (Windows) o lsb (Linux/Mac fallback)."""
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_VideoController | "
                 "Select-Object -ExpandProperty Name | ConvertTo-Json"],
                capture_output=True, text=True, timeout=5,
            )
            data = json.loads(result.stdout.strip() or "[]")
            if isinstance(data, str):
                data = [data]
            return [g for g in data if g and g.strip()]
        except Exception:
            return []
    # Linux/Mac: usar lspci o nvidia-smi como fallback básico
    try:
        result = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=5
        )
        return [
            line.strip()
            for line in result.stdout.splitlines()
            if any(k in line.lower() for k in ["vga", "3d", "display", "nvidia", "amd"])
        ]
    except Exception:
        return []


def _detect_cpu_sync() -> str:
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Get-WmiObject Win32_Processor).Name"],
                capture_output=True, text=True, timeout=5,
            )
            name = result.stdout.strip()
            if name:
                return name
        except Exception:
            pass
    return platform.processor() or "Procesador desconocido"


def _detect_hardware_sync() -> dict:
    gpus = _detect_gpus_sync()
    cpu = _detect_cpu_sync()
    ram_gb = round(psutil.virtual_memory().total / 1_073_741_824)  # bytes → GiB
    return {"cpu": cpu, "ram_gb": ram_gb, "gpus": gpus}


async def detect_hardware() -> dict:
    return await asyncio.to_thread(_detect_hardware_sync)


def _recommend_package(gpus: list[str]) -> str | None:
    """Devuelve el paquete onnxruntime recomendado según los gráficos detectados."""
    names = " ".join(gpus).lower()
    if "nvidia" in names:
        return "onnxruntime-gpu"
    if any(k in names for k in ["radeon", "amd", "intel arc", "intel uhd",
                                  "intel hd", "intel iris"]):
        return "onnxruntime-directml"
    return None


# Mapeo de identificadores cortos a paquetes/labels para el selector de provider
_PROVIDER_INFO = {
    "cpu":      {"label": "Procesador (CPU)",       "pkg": None},
    "cuda":     {"label": "GPU NVIDIA (CUDA)",       "pkg": "onnxruntime-gpu"},
    "directml": {"label": "GPU AMD/Intel (DirectML)", "pkg": "onnxruntime-directml"},
}

# Paquetes pip que componen el runtime CUDA (descarga sin admin)
_NVIDIA_CUDA_PKGS = [
    "nvidia-cublas-cu12",
    "nvidia-cuda-runtime-cu12",
    "nvidia-cuda-nvrtc-cu12",
    "nvidia-cudnn-cu12",
    "nvidia-cufft-cu12",
    "nvidia-curand-cu12",
    "nvidia-cusparse-cu12",
    "nvidia-nvjitlink-cu12",
]


def available_providers(gpus: list[str]) -> list[dict]:
    """Lista los providers disponibles para el hardware detectado.

    Devuelve objetos con: id, label, available (bool), reason (str|None).
    'cpu' siempre disponible. 'cuda' solo con NVIDIA. 'directml' con cualquier
    GPU en Windows.
    """
    names = " ".join(gpus).lower()
    has_nvidia = "nvidia" in names
    has_other_gpu = any(k in names for k in [
        "radeon", "amd", "intel arc", "intel uhd", "intel hd", "intel iris", "vega"
    ])
    is_windows = platform.system() == "Windows"

    providers = [{
        "id": "cpu",
        "label": _PROVIDER_INFO["cpu"]["label"],
        "available": True,
        "reason": None,
    }]

    providers.append({
        "id": "cuda",
        "label": _PROVIDER_INFO["cuda"]["label"],
        "available": has_nvidia,
        "reason": None if has_nvidia else "Requiere GPU NVIDIA",
    })

    providers.append({
        "id": "directml",
        "label": _PROVIDER_INFO["directml"]["label"],
        "available": is_windows and (has_nvidia or has_other_gpu),
        "reason": None if (is_windows and (has_nvidia or has_other_gpu))
                  else ("Requiere Windows + GPU" if not is_windows else "Sin GPU detectada"),
    })

    return providers


def active_provider_id(provider: str) -> str:
    """Mapea el provider ONNX activo al id corto usado por el selector."""
    return {
        "CUDAExecutionProvider": "cuda",
        "DirectMLExecutionProvider": "directml",
        "CPUExecutionProvider": "cpu",
    }.get(provider, "cpu")


# ---------------------------------------------------------------------------
# Estado de instalación GPU (compartido entre endpoint y tarea)
# ---------------------------------------------------------------------------

InstallStatus = Literal["idle", "installing", "done", "error"]
_install_status: InstallStatus = "idle"
_install_error: str | None = None

# Estado de instalacion de Docling (~2 GB, on-demand desde Settings RAG)
_docling_status: InstallStatus = "idle"
_docling_error: str | None = None


def get_install_status() -> dict:
    return {"status": _install_status, "error": _install_error}


def is_docling_installed() -> bool:
    import importlib.util
    return importlib.util.find_spec("docling") is not None


def get_docling_status() -> dict:
    return {
        "status": _docling_status,
        "error": _docling_error,
        "installed": is_docling_installed(),
    }


async def install_docling() -> None:
    """Instala docling (torch + transformers + modelos, ~2 GB) en background.

    No reinicia automaticamente — el usuario aplica useDocling=True desde
    Settings y eso ya dispara el reinicio normal del flujo de ajustes RAG."""
    global _docling_status, _docling_error
    _docling_status = "installing"
    _docling_error = None
    try:
        # docling trae torch como dep transitiva. Instalamos en una sola
        # invocacion para que pip resuelva versiones compatibles entre todas.
        await asyncio.to_thread(_pip_install_sync, ["docling"])
        _docling_status = "done"
    except Exception as exc:
        _docling_status = "error"
        _docling_error = str(exc)


# ---------------------------------------------------------------------------
# Instalación de paquete onnxruntime + reinicio graceful
# ---------------------------------------------------------------------------

def _pip_install_sync(pkgs: list[str]) -> None:
    if not pkgs:
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", *pkgs],
        check=True,
        timeout=900,  # 15 min (~1.9 GB CUDA wheels en primera instalación)
    )


def _pip_uninstall_sync(pkgs: list[str]) -> None:
    if not pkgs:
        return
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", "--quiet", *pkgs],
        check=False,
        timeout=120,
    )


def _is_installed(pkg: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "show", pkg],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0


async def install_gpu_package(pkg: str) -> None:
    """Compat: instala el paquete onnxruntime indicado en background y reinicia."""
    global _install_status, _install_error
    _install_status = "installing"
    _install_error = None
    try:
        pkgs = [pkg]
        if pkg == "onnxruntime-gpu":
            pkgs = _NVIDIA_CUDA_PKGS + ["onnxruntime-gpu"]
        await asyncio.to_thread(_pip_install_sync, pkgs)
        _install_status = "done"
    except Exception as exc:
        _install_status = "error"
        _install_error = str(exc)
        return
    asyncio.get_running_loop().call_later(_RESTART_DELAY_S, lambda: os._exit(99))


async def switch_provider(target: str) -> None:
    """Cambia el motor de procesamiento IA al provider indicado.

    target: 'auto' | 'cpu' | 'cuda' | 'directml'

    'auto' guarda la preferencia y reinicia para que start.bat autodetecte.
    El resto desinstala lo actual, instala lo necesario, guarda preferencia y reinicia.
    """
    global _install_status, _install_error
    if target not in _VALID_PREFS:
        raise ValueError(f"Provider desconocido: {target}")

    # Guardar preferencia primero — start.bat la lee en el siguiente arranque
    # para evitar que la autodeteccion sobreescriba la eleccion del usuario.
    save_provider_preference(target)

    _install_status = "installing"
    _install_error = None

    # Resolver target efectivo. "auto" se autodetecta en el momento — no basta
    # con guardar la preferencia porque start.bat solo se ejecuta en arranque
    # en frio, no en cada exit 99 + relaunch del backend.
    effective = target
    if target == "auto":
        gpus = await asyncio.to_thread(_detect_gpus_sync)
        names = " ".join(gpus).lower()
        if "nvidia" in names:
            effective = "cuda"
        elif any(k in names for k in [
            "radeon", "amd", "intel arc", "intel uhd",
            "intel hd", "intel iris", "vega",
        ]):
            effective = "directml"
        else:
            effective = "cpu"

    has_gpu = _is_installed("onnxruntime-gpu")
    has_dml = _is_installed("onnxruntime-directml")
    has_cuda_wheels = _is_installed("nvidia-cublas-cu12")

    to_uninstall: list[str] = []
    to_install: list[str] = []

    # Las wheels nvidia-* (cublas, cudnn, ...) son solo DLLs, no chocan con
    # ningun otro paquete: las dejamos instaladas siempre para evitar re-bajar
    # ~1.4 GB si el usuario vuelve a CUDA mas adelante.
    # Los paquetes onnxruntime-gpu / onnxruntime-directml / onnxruntime SI
    # chocan (mismo paquete Python con builds distintos): hay que desinstalar
    # el actual antes de instalar el nuevo.
    if effective == "cpu":
        if has_gpu: to_uninstall.append("onnxruntime-gpu")
        if has_dml: to_uninstall.append("onnxruntime-directml")
    elif effective == "cuda":
        if has_dml: to_uninstall.append("onnxruntime-directml")
        if not has_cuda_wheels: to_install.extend(_NVIDIA_CUDA_PKGS)
        if not has_gpu: to_install.append("onnxruntime-gpu")
    elif effective == "directml":
        if has_gpu: to_uninstall.append("onnxruntime-gpu")
        if not has_dml: to_install.append("onnxruntime-directml")

    # Si no hay nada que instalar/desinstalar el estado actual ya cumple — solo
    # guardar preferencia (ya hecho arriba) y marcar como listo sin reiniciar.
    if not to_install and not to_uninstall:
        _install_status = "done"
        return

    try:
        if to_uninstall:
            await asyncio.to_thread(_pip_uninstall_sync, to_uninstall)
        if to_install:
            await asyncio.to_thread(_pip_install_sync, to_install)
        _install_status = "done"
    except Exception as exc:
        _install_status = "error"
        _install_error = str(exc)
        return
    asyncio.get_running_loop().call_later(_RESTART_DELAY_S, lambda: os._exit(99))


def restart_app() -> None:
    """Reinicia SeekPal vía exit code 99 (start.bat lo detecta y relanza)."""
    asyncio.get_running_loop().call_later(_RESTART_DELAY_S, lambda: os._exit(99))


# ---------------------------------------------------------------------------
# Gestión de modelos de Ollama (panel "Modelos y almacenamiento")
# ---------------------------------------------------------------------------

_OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Modelo de respaldo que nunca se desinstala (más ligero, siempre disponible).
_FALLBACK_VISION_MODEL = "moondream"

# Catálogo de modelos conocidos: aparecen en el panel aunque no estén instalados.
_MODEL_CATALOG: list[dict] = [
    {"id": "qwen2.5vl:3b", "category": "vision", "label": "Visión · calidad"},
    {"id": "moondream",    "category": "vision", "label": "Visión · ligero (respaldo)"},
    {"id": "llama3.2:3b",  "category": "llm",    "label": "LLM · ligero (CPU/sin gráfica)"},
    {"id": "qwen3:4b",     "category": "llm",    "label": "LLM · calidad (requiere GPU/RAM)"},
]

# Orden del panel de modelos: primero por tipo, luego por potencia (de ligero a
# potente) dentro de cada tipo. Sustituye al antiguo "instalados primero", que
# dejaba un modelo suelto arriba (p. ej. Audio small) y el resto al fondo.
_CATEGORY_ORDER = {"llm": 0, "vision": 1, "audio": 2, "ocr": 3, "pdf": 4, "otro": 5}
_POWER_ORDER = {
    "llama3.2:3b": 0, "qwen3:4b": 1,
    "moondream": 0, "qwen2.5vl:3b": 1,
    "whisper:tiny": 0, "whisper:base": 1, "whisper:small": 2, "whisper:medium": 3,
    "ocr:mobile": 0, "ocr:server": 1,
    "docling": 0,
}

# Estado de la descarga en curso (patrón análogo a get_install_status).
_pull_status: dict = {"status": "idle", "model": None, "error": None}


def _norm_model(name: str) -> str:
    """Normaliza el nombre de un modelo Ollama quitando el sufijo ':latest'."""
    return name[:-7] if name.endswith(":latest") else name


def _ollama_client():
    from ollama import Client
    return Client(host=_OLLAMA_URL)


def _installed_models() -> dict[str, tuple[str, int | None]]:
    """{nombre_normalizado: (nombre_real, tamaño_bytes)} de lo instalado en Ollama.

    Devuelve {} si Ollama no está disponible (todo se mostrará como no instalado).
    Tolera las distintas formas de respuesta de la librería ollama (objeto/dict)."""
    out: dict[str, tuple[str, int | None]] = {}
    try:
        resp = _ollama_client().list()
        models = getattr(resp, "models", None)
        if models is None and isinstance(resp, dict):
            models = resp.get("models", [])
        for m in models or []:
            real = getattr(m, "model", None) or getattr(m, "name", None)
            size = getattr(m, "size", None)
            if real is None and isinstance(m, dict):
                real = m.get("model") or m.get("name")
                size = m.get("size")
            if isinstance(size, (int, float)):
                size = int(size)
            elif size is not None:
                size = getattr(size, "real", None) or None
            if real:
                out[_norm_model(real)] = (real, size)
    except Exception:
        pass
    return out


def _active_model_norms() -> set[str]:
    from app.core import runtime_settings
    from app.core.config import settings
    # LLM y visión activos según runtime_settings (lo que de verdad se usa),
    # con fallback al estático de .env. Se usan para proteger de borrado.
    active = {_norm_model(runtime_settings.get("llmModel", settings.llm_model))}
    vm = runtime_settings.get("visionModel")
    if vm:
        active.add(_norm_model(vm))
    return active


# ── Whisper (faster-whisper) — modelos en la caché de HuggingFace ──────────
_WHISPER_SIZES = ["tiny", "base", "small", "medium"]
_WHISPER_SIZE_HINT = {  # tamaño aprox. para mostrar antes de instalar
    "tiny": 75_000_000, "base": 145_000_000, "small": 488_000_000, "medium": 1_530_000_000,
}


def _whisper_cache() -> dict[str, int]:
    """{size: bytes_en_disco} de los modelos faster-whisper en la caché de HF."""
    out: dict[str, int] = {}
    try:
        from huggingface_hub import scan_cache_dir
        for repo in scan_cache_dir().repos:
            rid = repo.repo_id.lower()
            for size in _WHISPER_SIZES:
                if rid.endswith(f"faster-whisper-{size}"):
                    out[size] = int(repo.size_on_disk)
    except Exception:
        pass
    return out


def _whisper_delete(size: str) -> None:
    from huggingface_hub import scan_cache_dir
    info = scan_cache_dir()
    revs = [
        rev.commit_hash
        for repo in info.repos if repo.repo_id.lower().endswith(f"faster-whisper-{size}")
        for rev in repo.revisions
    ]
    if revs:
        info.delete_revisions(*revs).execute()


def _whisper_models() -> list[dict]:
    from app.core import runtime_settings
    installed = _whisper_cache()
    active = runtime_settings.get("whisperModel", "small")
    out = []
    for size in _WHISPER_SIZES:
        is_inst = size in installed
        is_active = size == active
        out.append({
            "id": f"whisper:{size}", "manager": "whisper", "category": "audio",
            "label": f"Audio · {size}",
            "sizeBytes": installed.get(size) if is_inst else _WHISPER_SIZE_HINT[size],
            "installed": is_inst, "active": is_active,
            "protected": is_active, "deletable": is_inst and not is_active,
        })
    return out


# ── OCR (rapidocr) — modelos onnx en el paquete ────────────────────────────
_OCR_SERVER_FILES = ["ch_PP-OCRv4_det_server.onnx", "ch_PP-OCRv4_rec_server.onnx"]


def _ocr_models_dir() -> Path | None:
    import importlib.util
    for pkg in ("rapidocr_onnxruntime", "rapidocr"):
        try:
            spec = importlib.util.find_spec(pkg)
        except Exception:
            spec = None
        if spec and spec.origin:
            return Path(spec.origin).parent / "models"
    return None


def _ocr_delete_server() -> None:
    mdir = _ocr_models_dir()
    if not mdir:
        return
    for f in _OCR_SERVER_FILES:
        p = mdir / f
        if p.exists():
            p.unlink()


def _ocr_models() -> list[dict]:
    from app.core import runtime_settings
    active = runtime_settings.get("ocrQuality", "mobile")
    mdir = _ocr_models_dir()
    server_paths = [mdir / f for f in _OCR_SERVER_FILES] if mdir else []
    server_inst = bool(server_paths) and all(p.exists() for p in server_paths)
    server_size = sum(p.stat().st_size for p in server_paths if p.exists()) if server_inst else 140_000_000
    return [
        {"id": "ocr:mobile", "manager": "ocr", "category": "ocr", "label": "OCR · rápido (incluido)",
         "sizeBytes": None, "installed": True, "active": active == "mobile",
         "protected": True, "deletable": False},
        {"id": "ocr:server", "manager": "ocr", "category": "ocr", "label": "OCR · preciso",
         "sizeBytes": server_size, "installed": server_inst, "active": active == "server",
         "protected": active == "server", "deletable": server_inst and active != "server"},
    ]


# ── Docling — paquete pip (~2 GB) ──────────────────────────────────────────
def _docling_models() -> list[dict]:
    from app.core import runtime_settings
    inst = is_docling_installed()
    active = bool(runtime_settings.get("useDocling", False))
    return [{
        "id": "docling", "manager": "docling", "category": "pdf",
        "label": "PDFs estructurados (Docling)",
        "sizeBytes": 2_000_000_000,  # ~2 GB (torch + transformers + modelos), estimado
        "installed": inst, "active": active,
        "protected": active, "deletable": inst and not active,
        # Eliminar Docling hace `pip uninstall docling`, que NO quita sus
        # dependencias pesadas (torch + transformers, ~2 GB): solo libera el
        # paquete docling (decenas de MB). El tamaño de arriba es el coste de
        # instalación, no lo que se recupera al borrar.
        "deleteNote": (
            "Eliminar solo desinstala el paquete Docling; las dependencias "
            "pesadas (torch, transformers; ~2 GB) permanecen porque pueden "
            "estar compartidas. Libera poco espacio."
        ),
    }]


def _find_item(model_id: str) -> dict | None:
    return next(
        (m for m in list_models() if m["id"] == model_id or _norm_model(m["id"]) == _norm_model(model_id)),
        None,
    )


def list_models() -> list[dict]:
    """Catálogo de modelos para el panel: instalados y no instalados.

    Cada item: {id, manager, category, label, sizeBytes, installed, active, protected, deletable}.
    Cubre Ollama (LLM/visión), Whisper (audio), OCR y Docling. Orden: por tipo y
    potencia. Protegidos = modelo activo o de respaldo (no se pueden eliminar)."""
    installed = _installed_models()
    active = _active_model_norms()
    fallback = _norm_model(_FALLBACK_VISION_MODEL)

    out: list[dict] = []
    seen: set[str] = set()
    for entry in _MODEL_CATALOG:
        nid = _norm_model(entry["id"])
        seen.add(nid)
        real, size = installed.get(nid, (None, None))
        is_inst = real is not None
        is_active = nid in active
        protected = is_active or nid == fallback
        out.append({
            "id": entry["id"],
            "manager": "ollama",
            "category": entry["category"],
            "label": entry["label"],
            "sizeBytes": size,
            "installed": is_inst,
            "active": is_active,
            "protected": protected,
            "deletable": is_inst and not protected,
        })

    # Modelos instalados que no están en el catálogo (restos: bge-m3, llama3.2…).
    for nid, (real, size) in installed.items():
        if nid in seen:
            continue
        is_active = nid in active
        protected = is_active or nid == fallback
        out.append({
            "id": real,
            "manager": "ollama",
            "category": "otro",
            "label": real,
            "sizeBytes": size,
            "installed": True,
            "active": is_active,
            "protected": protected,
            "deletable": not protected,
        })

    out.extend(_whisper_models())
    out.extend(_ocr_models())
    out.extend(_docling_models())

    # Orden: por tipo y, dentro de cada tipo, por potencia (ligero -> potente).
    out.sort(key=lambda x: (
        _CATEGORY_ORDER.get(x["category"], 99),
        _POWER_ORDER.get(x["id"], 99),
        x["label"],
    ))
    return out


def delete_model(model_id: str) -> dict:
    """Desinstala un modelo (cualquier manager). Rechaza los protegidos (activo o
    respaldo) y si hay una ingesta en curso (podría estar usándolo)."""
    from app.services import scanner_service
    if scanner_service.is_ingesting():
        raise ValueError("No se puede eliminar un modelo mientras hay una ingesta en curso")
    item = _find_item(model_id)
    if item is None or not item["installed"]:
        raise ValueError("El modelo no está instalado")
    if not item["deletable"]:
        raise ValueError("Modelo en uso o de respaldo: no se puede eliminar")
    mgr = item["manager"]
    if mgr == "ollama":
        _ollama_client().delete(item["id"])
    elif mgr == "whisper":
        _whisper_delete(item["id"].split(":", 1)[1])
    elif mgr == "ocr":
        _ocr_delete_server()
    elif mgr == "docling":
        _pip_uninstall_sync(["docling"])
    else:
        raise ValueError("Este modelo no se puede eliminar")
    return {"deleted": item["id"]}


def free_vision_model(model_id: str) -> None:
    """Borra un modelo de visión que se deja de usar (toggle auto-liberar).

    Se llama al cambiar visionModel, ANTES del reinicio, así que no se apoya en el
    check de 'active' de runtime_settings (aún apunta al modelo viejo). Protege el
    respaldo (moondream) y el LLM activo. Fallo no crítico."""
    from app.core.config import settings
    from app.core import runtime_settings
    from app.services import scanner_service
    # Nunca borrar durante una ingesta: el captioning podría estar usando el
    # modelo anterior justo ahora (el cambio de modelo solo se aplica al reiniciar).
    if scanner_service.is_ingesting():
        return
    llm = runtime_settings.get("llmModel", settings.llm_model)
    protected = {_norm_model(_FALLBACK_VISION_MODEL), _norm_model(llm)}
    if _norm_model(model_id) in protected:
        return
    try:
        _ollama_client().delete(model_id)
    except Exception:
        pass


def get_pull_status() -> dict:
    return dict(_pull_status)


def _install_sync(item: dict) -> None:
    mgr = item["manager"]
    if mgr == "ollama":
        _ollama_client().pull(item["id"])
    elif mgr == "whisper":
        from huggingface_hub import snapshot_download
        size = item["id"].split(":", 1)[1]
        snapshot_download(f"Systran/faster-whisper-{size}")
    elif mgr == "ocr":
        from app.services.rag.image_service import _ensure_server_models
        _ensure_server_models()
    elif mgr == "docling":
        _pip_install_sync(["docling"])
    else:
        raise ValueError(f"No se sabe instalar el modelo: {item['id']}")


async def pull_model(model_id: str) -> None:
    """Descarga/instala un modelo (cualquier manager) en background."""
    global _pull_status
    item = _find_item(model_id)
    if item is None:
        _pull_status = {"status": "error", "model": model_id, "error": "Modelo desconocido"}
        return
    _pull_status = {"status": "pulling", "model": model_id, "error": None}
    try:
        await asyncio.to_thread(_install_sync, item)
        _pull_status = {"status": "done", "model": model_id, "error": None}
    except Exception as exc:  # noqa: BLE001
        _pull_status = {"status": "error", "model": model_id, "error": str(exc)}


def is_known_model(model_id: str) -> bool:
    """True si el modelo está en el catálogo o ya instalado (evita pulls arbitrarios)."""
    return any(
        m["id"] == model_id or _norm_model(m["id"]) == _norm_model(model_id)
        for m in list_models()
    )
