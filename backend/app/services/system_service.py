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
