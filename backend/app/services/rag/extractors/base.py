from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.services.rag.types import ExtractedDoc


class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, path: Path) -> ExtractedDoc: ...

    @abstractmethod
    def supported_extensions(self) -> list[str]: ...
