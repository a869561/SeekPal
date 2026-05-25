"""Configuracion central de logging para SeekPal.

Sustituye los print('[seekpal] ...') dispersos por el modulo logging estandar
con niveles (DEBUG/INFO/WARNING/ERROR/CRITICAL) y formato uniforme.

Uso desde otros modulos:
    import logging
    logger = logging.getLogger("seekpal.<subsystem>")
    logger.info("Mensaje informativo")
    logger.warning("Algo raro pero no critico")
    logger.error("Algo fallo")
"""

from __future__ import annotations

import logging
import os
import sys


_CONFIGURED = False


def setup_logging() -> None:
    """Configura el root logger 'seekpal'. Idempotente."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.getenv("SEEKPAL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    logger = logging.getLogger("seekpal")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False  # Evita logs duplicados con uvicorn

    # Silenciar dependencias verbose en INFO
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("watchdog").setLevel(logging.WARNING)

    _CONFIGURED = True
