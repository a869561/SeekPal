"""Cliente de embeddings sobre la API de Ollama (BGE-M3, dim=1024).

BGE-M3 no requiere prefijos de query especiales (distinto de E5), por lo que
embed_texts y embed_query usan el mismo endpoint sin modificar el input.
"""

from __future__ import annotations

from ollama import AsyncClient


class EmbeddingService:
    def __init__(self, base_url: str, model: str, batch_size: int):
        self._client = AsyncClient(host=base_url, timeout=60.0)
        self._model = model
        self._batch_size = batch_size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            resp = await self._client.embed(model=self._model, input=batch)
            out.extend(resp["embeddings"])
        return out

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]
