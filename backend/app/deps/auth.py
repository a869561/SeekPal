"""Dependencia de autenticación JWT (Bearer).

Usa `HTTPBearer` de FastAPI para que el esquema de seguridad quede registrado en
el OpenAPI: así Swagger UI (`/docs`) muestra el botón **Authorize** y la
documentación del API refleja que los endpoints están protegidos. La validación
del token y el formato de error (`{success, message}` en español) los seguimos
gestionando nosotros con `APIError`.
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.responses import APIError
from app.core.security import decode_access_token

# auto_error=False: no dejamos que HTTPBearer lance su propio 403; gestionamos el
# 401 nosotros para mantener el mensaje en español y el formato de respuesta. El
# esquema se registra igualmente en OpenAPI (botón Authorize en Swagger).
_bearer = HTTPBearer(
    auto_error=False,
    description="Token JWT obtenido en POST /api/auth/login (campo data.accessToken).",
)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise APIError("Token no proporcionado", status_code=401)
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise APIError(str(exc), status_code=401) from exc
