from app.models.config import UserSettings
from app.schemas.source import SettingsPatch


def test_user_settings_accepts_arbitrary_model_names():
    s = UserSettings(visionModel="gemma3:4b", whisperModel="Systran/faster-whisper-large-v3")
    assert s.visionModel == "gemma3:4b"
    assert s.whisperModel == "Systran/faster-whisper-large-v3"


def test_settings_patch_accepts_arbitrary_model_names():
    p = SettingsPatch(visionModel="llava:13b", whisperModel="large-v3")
    assert p.visionModel == "llava:13b"
    assert p.whisperModel == "large-v3"
