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
    for key, value in data.items():
        if value is not None:
            setattr(config.settings, key, value)
    await config.save()
    return ok(config.settings.model_dump())
