"""Smoke tests para los servicios multimedia (audio, image, video).

No cargan los modelos reales (Whisper, RapidOCR, Moondream). Verifican:
  - Degradacion correcta cuando los modelos no estan disponibles
  - Combinacion OCR + caption en extract_image_text
  - Estructura de los extractores (interfaz BaseExtractor + extensiones)
  - Resolucion de timeouts y configs runtime
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# AudioExtractor / audio_service
# ---------------------------------------------------------------------------

def test_audio_extractor_extensions_match_classifier():
    """El AudioExtractor cubre las mismas extensiones que mime_classifier."""
    from app.services.rag.extractors.audio import AudioExtractor
    from app.utils.mime_classifier import AUDIO_EXTENSIONS

    ext_list = set(AudioExtractor().supported_extensions())
    assert ext_list == AUDIO_EXTENSIONS, (
        f"AudioExtractor cubre {ext_list - AUDIO_EXTENSIONS} de mas o "
        f"{AUDIO_EXTENSIONS - ext_list} de menos"
    )


def test_audio_transcribe_returns_empty_when_whisper_unavailable(tmp_path: Path):
    """Si Whisper no carga, transcribe() devuelve "" sin lanzar excepcion."""
    from app.services.rag import audio_service

    fake_audio = tmp_path / "test.mp3"
    fake_audio.write_bytes(b"fake mp3 data")

    with patch.object(audio_service, "get_whisper", return_value=None):
        result = audio_service.transcribe(fake_audio)
        assert result == ""


def test_audio_extractor_uses_audio_extractor_name():
    """El campo extractor de ExtractedDoc identifica la fuente."""
    from app.services.rag.extractors import audio as audio_extractor_mod

    with patch.object(audio_extractor_mod, "transcribe", return_value="hola mundo"):
        doc = audio_extractor_mod.AudioExtractor().extract(Path("/tmp/fake.mp3"))
        assert doc.extractor == "audio"
        assert doc.text == "hola mundo"


# ---------------------------------------------------------------------------
# ImageExtractor / image_service
# ---------------------------------------------------------------------------

def test_image_extractor_extensions_subset_of_classifier():
    """ImageExtractor cubre formatos rasterizados (no SVG/ICO que son vectoriales)."""
    from app.services.rag.extractors.image import ImageExtractor
    from app.utils.mime_classifier import IMAGE_EXTENSIONS

    ext_list = set(ImageExtractor().supported_extensions())
    # SVG e ICO se clasifican como image pero no se indexan (vectoriales)
    excluded = {".svg", ".ico"}
    expected = IMAGE_EXTENSIONS - excluded
    assert ext_list == expected, (
        f"ImageExtractor cubre {ext_list - expected} de mas o "
        f"{expected - ext_list} de menos"
    )


def test_extract_image_text_combines_caption_and_ocr():
    """extract_image_text concatena descripcion + texto OCR cuando ambos existen."""
    from app.services.rag import image_service

    with patch.object(image_service, "caption_image", return_value="Una foto de un gato"), \
         patch.object(image_service, "ocr_image", return_value="texto en cartel"):
        result = image_service.extract_image_text(Path("/tmp/fake.png"))
        assert "Descripcion: Una foto de un gato" in result
        assert "Texto en la imagen: texto en cartel" in result


def test_extract_image_text_handles_empty_caption():
    """Si caption falla pero OCR funciona, devuelve solo OCR."""
    from app.services.rag import image_service

    with patch.object(image_service, "caption_image", return_value=""), \
         patch.object(image_service, "ocr_image", return_value="hello world"):
        result = image_service.extract_image_text(Path("/tmp/fake.png"))
        assert "Texto en la imagen: hello world" in result
        assert "Descripcion:" not in result


def test_extract_image_text_handles_both_empty():
    """Sin caption ni OCR, devuelve cadena vacia (no crashea)."""
    from app.services.rag import image_service

    with patch.object(image_service, "caption_image", return_value=""), \
         patch.object(image_service, "ocr_image", return_value=""):
        result = image_service.extract_image_text(Path("/tmp/fake.png"))
        assert result == ""


# ---------------------------------------------------------------------------
# _sanitize_caption: rechazo de salidas degeneradas del VLM
# ---------------------------------------------------------------------------

def test_sanitize_caption_rejects_special_token_spam():
    """qwen2.5vl degenera y emite '<|im_start|>' en bucle -> se descarta como vacío."""
    from app.services.rag.image_service import _sanitize_caption

    garbage = "<|im_start|> " * 30
    assert _sanitize_caption(garbage) == ""


def test_sanitize_caption_strips_tokens_keeps_real_text():
    """Si hay texto real mezclado con tokens, se conserva el texto sin los tokens."""
    from app.services.rag.image_service import _sanitize_caption

    mixed = "<|im_start|> Una captura de los rangos de Valorant <|im_end|>"
    out = _sanitize_caption(mixed)
    assert "im_start" not in out and "im_end" not in out
    assert "rangos de Valorant" in out


def test_sanitize_caption_rejects_placeholder_oneliner():
    """Salidas degeneradas tipo '!!!IMAGES!!!' (token suelto) se descartan."""
    from app.services.rag.image_service import _sanitize_caption

    assert _sanitize_caption("!!!IMAGES!!!") == ""


def test_sanitize_caption_rejects_repetition_loop():
    """Una palabra repetida en bucle no es una descripción válida."""
    from app.services.rag.image_service import _sanitize_caption

    assert _sanitize_caption("rango " * 12) == ""


def test_sanitize_caption_keeps_normal_caption():
    """Un caption normal pasa intacto (salvo normalización de espacios)."""
    from app.services.rag.image_service import _sanitize_caption

    cap = "Una fotografía de un gato negro sentado en un sofá."
    assert _sanitize_caption(cap) == cap


# ---------------------------------------------------------------------------
# VideoExtractor
# ---------------------------------------------------------------------------

def test_video_extractor_extensions_match_classifier():
    from app.services.rag.extractors.video import VideoExtractor
    from app.utils.mime_classifier import VIDEO_EXTENSIONS

    ext_list = set(VideoExtractor().supported_extensions())
    assert ext_list == VIDEO_EXTENSIONS


def test_video_frame_interval_reads_runtime_settings(monkeypatch):
    """El intervalo de frames respeta runtime_settings."""
    from app.core import runtime_settings
    from app.services.rag.extractors import video

    monkeypatch.delenv("SEEKPAL_VIDEO_FRAME_INTERVAL", raising=False)
    original = runtime_settings._settings.get("videoFrameInterval")
    try:
        runtime_settings._settings["videoFrameInterval"] = 45
        assert video._frame_interval() == 45
    finally:
        runtime_settings._settings["videoFrameInterval"] = original or 30


def test_video_env_override_takes_priority(monkeypatch):
    """SEEKPAL_VIDEO_FRAME_INTERVAL tiene prioridad sobre runtime_settings."""
    from app.services.rag.extractors import video

    monkeypatch.setenv("SEEKPAL_VIDEO_FRAME_INTERVAL", "60")
    assert video._frame_interval() == 60


def test_video_extractor_returns_extractor_field():
    """Aun sin ffmpeg disponible, extract() devuelve ExtractedDoc con extractor='video'."""
    from app.services.rag.extractors import video

    # Sin parchear ffmpeg, _extract_audio devuelve False y no hay frames
    with patch.object(video, "_extract_audio", return_value=False), \
         patch.object(video, "_extract_frames", return_value=[]):
        doc = video.VideoExtractor().extract(Path("/tmp/fake.mp4"))
        assert doc.extractor == "video"
        assert doc.text == ""  # sin audio ni frames -> vacio
