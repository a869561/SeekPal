from fastapi import Header

from app.core.responses import APIError
from app.core.security import decode_access_token


async def require_auth(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise APIError("Token no proporcionado", status_code=401)
    token = authorization.split(" ", 1)[1]
    try:
        return decode_access_token(token)
    except ValueError as exc:
        raise APIError(str(exc), status_code=401) from exc
