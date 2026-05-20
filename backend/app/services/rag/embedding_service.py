"""Cliente de embeddings sobre la API de Ollama (BGE-M3, dim=1024).

BGE-M3 no requiere prefijos de query especiales (distinto de E5), por lo que
embed_texts y embed_query usan el mismo endpoint sin modificar el input.
"""

from __future__ import annotations

import re
import unicodedata

from ollama import AsyncClient

# Caracteres de control que confunden al tokenizador de BGE-M3 y causan NaN
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _sanitize(text: str) -> str:
    """Normaliza unicode, elimina caracteres de control y colapsa espacios."""
    text = unicodedata.normalize("NFC", text)
    text = _CTRL.sub(" ", text)
    return " ".join(text.split())


class EmbeddingService:
    def __init__(self, base_url: str, model: str, batch_size: int):
        self._client = AsyncClient(host=base_url, timeout=60.0)
        self._model = model
        self._batch_size = batch_size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        sanitized = [_sanitize(t) for t in texts]
        out: list[list[float]] = []
        for i in range(0, len(sanitized), self._batch_size):
            batch = sanitized[i : i + self._batch_size]
            try:
                resp = await self._client.embed(model=self._model, input=batch)
                out.extend(resp["embeddings"])
            except Exception:
                # Batch failed (posiblemente NaN en algún item): reintentar uno a uno
                for item in batch:
                    resp = await self._client.embed(model=self._model, input=[item])
                    out.append(resp["embeddings"][0])
        return out

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]
