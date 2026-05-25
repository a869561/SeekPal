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
from typing import Literal

import psutil


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


# ---------------------------------------------------------------------------
# Estado de instalación GPU (compartido entre endpoint y tarea)
# ---------------------------------------------------------------------------

InstallStatus = Literal["idle", "installing", "done", "error"]
_install_status: InstallStatus = "idle"
_install_error: str | None = None


def get_install_status() -> dict:
    return {"status": _install_status, "error": _install_error}


# ---------------------------------------------------------------------------
# Instalación de paquete onnxruntime + reinicio graceful
# ---------------------------------------------------------------------------

def _install_pkg_sync(pkg: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "--quiet"],
        check=True,
        timeout=600,  # 10 min máximo (paquetes GPU pueden ser ~500 MB)
    )


async def install_gpu_package(pkg: str) -> None:
    """Instala el paquete onnxruntime indicado en background y luego reinicia."""
    global _install_status, _install_error
    _install_status = "installing"
    _install_error = None
    try:
        await asyncio.to_thread(_install_pkg_sync, pkg)
        _install_status = "done"
    except Exception as exc:
        _install_status = "error"
        _install_error = str(exc)
        return
    # Reinicio graceful: exit code 99 → start.bat lo relanza
    asyncio.get_event_loop().call_later(0.3, lambda: os._exit(99))


def restart_app() -> None:
    """Reinicia SeekPal vía exit code 99 (start.bat lo detecta y relanza)."""
    asyncio.get_event_loop().call_later(0.3, lambda: os._exit(99))
