"""Helper para servicios cargados perezosamente (Whisper, RapidOCR, ...).

Encapsula el patron repetido "singleton + lock + disabled flag":

  - Primera llamada -> intenta cargar (puede fallar por dependencia ausente,
    sin red, modelo no descargado).
  - Si la carga falla -> marca el servicio como deshabilitado para no
    reintentar (evita logs ruidosos en cada fichero procesado).
  - Llamadas siguientes -> devuelven la instancia cacheada.

Es thread-safe (lock externo) y para uso desde funciones sincronas. Los
servicios async que solo necesitan inicializacion ligera (ej. cliente HTTP)
pueden usarlo igual porque la fabrica devuelve cualquier objeto.
"""

from __future__ import annotations

from threading import Lock
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


class LazyService(Generic[T]):
    """Cache un objeto creado por `factory()` la primera vez que se pide.

    Si `factory()` lanza, marca el servicio como deshabilitado y devuelve
    `None` en las siguientes llamadas a `get()` sin reintentar.
    """

    __slots__ = ("_factory", "_name", "_lock", "_instance", "_disabled")

    def __init__(self, name: str, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._name = name
        self._lock = Lock()
        self._instance: T | None = None
        self._disabled = False

    def get(self) -> T | None:
        if self._disabled:
            return None
        if self._instance is not None:
            return self._instance
        with self._lock:
            if self._instance is not None:
                return self._instance
            try:
                self._instance = self._factory()
            except Exception as exc:  # noqa: BLE001
                print(f"[seekpal] {self._name}: error al inicializar — {exc}")
                self._disabled = True
                return None
        return self._instance

    def disable(self) -> None:
        """Marca el servicio como no-funcional (p.ej. modelo no descargado).

        Util para errores que se descubren solo al usar el servicio (no al
        cargarlo). El siguiente `get()` devolvera None sin reintentar."""
        self._disabled = True

    @property
    def disabled(self) -> bool:
        return self._disabled
