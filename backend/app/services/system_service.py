"""Servicios del sistema (selector de carpeta nativo, etc.).

El diálogo de selección de carpeta se ejecuta en un subproceso Python con
tkinter para ser multiplataforma y no bloquear el event loop de FastAPI.
"""

import asyncio
import subprocess
import sys


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
