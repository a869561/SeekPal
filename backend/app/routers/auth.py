from fastapi import APIRouter, Depends

from app.core.responses import ok
from app.deps.auth import require_auth
from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest):
    token = await auth_service.login(body.password)
    return ok(token, "Login correcto")


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    _user: dict = Depends(require_auth),
):
    await auth_service.change_password(body.currentPassword, body.newPassword)
    return ok(None, "Contraseña actualizada")
