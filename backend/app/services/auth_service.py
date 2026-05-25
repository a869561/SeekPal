import logging

from app.core.config import settings
from app.core.responses import APIError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.config import Config

logger = logging.getLogger("seekpal.auth")


async def get_or_create_config() -> Config:
    config = await Config.find_one()
    if config is None:
        config = Config(passwordHash=hash_password(settings.default_password))
        await config.insert()
        logger.info('Contraseña por defecto inicializada: "%s"', settings.default_password)
    return config


async def login(password: str) -> dict:
    config = await get_or_create_config()
    if not verify_password(password, config.passwordHash):
        raise APIError("Contraseña incorrecta", status_code=401)
    token = create_access_token()
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresIn": f"{settings.jwt_expires_minutes}m",
    }


async def change_password(current: str, new: str) -> None:
    config = await get_or_create_config()
    if not verify_password(current, config.passwordHash):
        raise APIError("Contraseña actual incorrecta", status_code=401)
    config.passwordHash = hash_password(new)
    await config.save()
