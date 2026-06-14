from fastapi import APIRouter, Depends

from app.core.responses import ok
from app.deps.auth import require_auth
from app.schemas.source import SettingsPatch
from app.services.auth_service import get_or_create_config

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_auth)])


@router.get("")
async def get_settings():
    config = await get_or_create_config()
    return ok(config.settings.model_dump())


@router.patch("")
async def update_settings(patch: SettingsPatch):
    config = await get_or_create_config()
    data = patch.model_dump(exclude_unset=True)
    old_vision = config.settings.visionModel
    for key, value in data.items():
        if value is not None:
            setattr(config.settings, key, value)
    await config.save()

    # Auto-liberar el modelo de visión anterior si el usuario activó el toggle.
    # Se hace tras guardar y antes del reinicio que dispara el frontend; el
    # helper protege el respaldo (moondream) y el LLM activo. Fallo no crítico.
    if (
        config.settings.autoFreePreviousVisionModel
        and "visionModel" in data
        and old_vision
        and old_vision != config.settings.visionModel
    ):
        try:
            from app.services import system_service
            system_service.free_vision_model(old_vision)
        except Exception:
            pass

    return ok(config.settings.model_dump())
