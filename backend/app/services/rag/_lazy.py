"""Helper para servicios cargados perezosamente (Whisper, RapidOCR, Docling, ...).

Encapsula el patron repetido "singleton + lock + disabled flag":

  - Primera llamada -> intenta cargar (puede fallar por dependencia ausente,
    sin red, modelo no descargado).
  - Si la carga falla -> marca el servicio como deshabilitado para no
    reintentar (evita logs ruidosos en cada fichero procesado).
  - Llamadas siguientes -> devuelven la instancia cacheada.

Es thread-safe (lock externo) y para uso desde funciones sincronas. Los
servicios async que solo necesitan inicializacion ligera (ej. cliente HTTP)
pueden usarlo igual porque la fabrica devuelve cualquier objeto.

Registro global (MODEL_REGISTRY):
  Los servicios llaman a register() para declararse. Cualquier componente
  puede consultar get_model_status() para saber que modelos estan cargando
  o cargados — util para mostrar indicadores de progreso en la UI.
"""

from __future__ import annotations

import logging
from threading import Lock
from typing import Callable, Generic, TypeVar

logger = logging.getLogger("seekpal.lazy")

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Registro global de servicios lazy
# ---------------------------------------------------------------------------

# Mapea nombre → LazyService para que get_model_status() pueda consultarlos
_registry: dict[str, "LazyService"] = {}


def register(service: "LazyService") -> "LazyService":
    """Registra un LazyService en el registro global y lo devuelve (fluent)."""
    _registry[service._name] = service
    return service


def get_model_status() -> dict[str, str]:
    """Estado de todos los modelos lazy registrados.

    Valores posibles:
      "pending"  → nunca se ha intentado cargar
      "loading"  → cargando ahora (factory() en ejecucion)
      "ready"    → cargado correctamente, listo para usar
      "disabled" → fallo al cargar o deshabilitado manualmente
    """
    status = {}
    for name, svc in _registry.items():
        if svc._disabled:
            status[name] = "disabled"
        elif svc._loading:
            status[name] = "loading"
        elif svc._instance is not None:
            status[name] = "ready"
        else:
            status[name] = "pending"
    return status


# ---------------------------------------------------------------------------
# LazyService
# ---------------------------------------------------------------------------

class LazyService(Generic[T]):
    """Cache un objeto creado por `factory()` la primera vez que se pide.

    Si `factory()` lanza, marca el servicio como deshabilitado y devuelve
    `None` en las siguientes llamadas a `get()` sin reintentar.

    Atributos publicos observables:
      loading  → True mientras factory() esta en ejecucion
      disabled → True si la carga fallo o se deshabilito manualmente
      ready    → True si la instancia esta lista para usar
    """

    __slots__ = ("_factory", "_name", "_lock", "_instance", "_disabled", "_loading")

    def __init__(self, name: str, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._name = name
        self._lock = Lock()
        self._instance: T | None = None
        self._disabled = False
        self._loading = False

    @property
    def loading(self) -> bool:
        return self._loading

    @property
    def disabled(self) -> bool:
        return self._disabled

    @property
    def ready(self) -> bool:
        return self._instance is not None

    def get(self) -> T | None:
        if self._disabled:
            return None
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is not None:
                return self._instance
            self._loading = True
            try:
                self._instance = self._factory()
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s: error al inicializar — %s", self._name, exc)
                self._disabled = True
                return None
            finally:
                self._loading = False
        return self._instance

    def disable(self) -> None:
        """Marca el servicio como no-funcional (p.ej. modelo no descargado).

        Util para errores que se descubren solo al usar el servicio (no al
        cargarlo). El siguiente `get()` devolvera None sin reintentar."""
        self._disabled = True
