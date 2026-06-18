from unittest.mock import MagicMock, patch

from app.services import system_service as ss


def _show_response(caps):
    r = MagicMock()
    r.capabilities = caps
    return r


def test_categorize_vision_model():
    ss._caps_cache.clear()
    client = MagicMock()
    client.show.return_value = _show_response(["completion", "vision"])
    with patch.object(ss, "_ollama_client", return_value=client):
        assert ss.categorize_ollama("gemma3:4b") == "vision"


def test_categorize_text_model():
    ss._caps_cache.clear()
    client = MagicMock()
    client.show.return_value = _show_response(["completion", "tools"])
    with patch.object(ss, "_ollama_client", return_value=client):
        assert ss.categorize_ollama("llama3.2:3b") == "llm"


def test_categorize_unknown_when_show_fails():
    ss._caps_cache.clear()
    client = MagicMock()
    client.show.side_effect = RuntimeError("ollama down")
    with patch.object(ss, "_ollama_client", return_value=client):
        assert ss.categorize_ollama("mistery:1b") == "otro"


def test_capabilities_are_cached():
    ss._caps_cache.clear()
    client = MagicMock()
    client.show.return_value = _show_response(["completion"])
    with patch.object(ss, "_ollama_client", return_value=client):
        ss.ollama_capabilities("llama3.2:3b")
        ss.ollama_capabilities("llama3.2:3b")
        assert client.show.call_count == 1
