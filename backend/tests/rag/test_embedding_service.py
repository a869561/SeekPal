from unittest.mock import AsyncMock, patch

from app.services.rag.embedding_service import EmbeddingService


async def test_embed_batch_returns_vectors():
    fake_resp = {"embeddings": [[0.1] * 1024, [0.2] * 1024]}
    with patch("app.services.rag.embedding_service.AsyncClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.embed = AsyncMock(return_value=fake_resp)
        svc = EmbeddingService(base_url="http://x", model="bge-m3", batch_size=2)
        vectors = await svc.embed_texts(["hola", "mundo"])
        assert vectors == [[0.1] * 1024, [0.2] * 1024]


async def test_embed_query_single_string():
    fake_resp = {"embeddings": [[0.5] * 1024]}
    with patch("app.services.rag.embedding_service.AsyncClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.embed = AsyncMock(return_value=fake_resp)
        svc = EmbeddingService(base_url="http://x", model="bge-m3", batch_size=32)
        vec = await svc.embed_query("pregunta")
        assert len(vec) == 1024


async def test_embed_batches_when_input_exceeds_batch_size():
    call_log: list[list[str]] = []

    async def fake_embed(model, input):
        call_log.append(input)
        return {"embeddings": [[0.0] * 1024 for _ in input]}

    with patch("app.services.rag.embedding_service.AsyncClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.embed = AsyncMock(side_effect=fake_embed)
        svc = EmbeddingService(base_url="http://x", model="bge-m3", batch_size=2)
        vectors = await svc.embed_texts(["a", "b", "c", "d", "e"])
        assert len(vectors) == 5
        assert [len(b) for b in call_log] == [2, 2, 1]


async def test_empty_input_returns_empty_list():
    with patch("app.services.rag.embedding_service.AsyncClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.embed = AsyncMock()
        svc = EmbeddingService(base_url="http://x", model="bge-m3", batch_size=32)
        result = await svc.embed_texts([])
        assert result == []
        mock_client.embed.assert_not_called()
