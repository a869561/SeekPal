from fastapi import APIRouter, Depends

from app.core.responses import APIError, ok
from app.deps.auth import require_auth
from app.services import system_service

router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(require_auth)])


@router.get("/folder-picker")
async def folder_picker():
    try:
        path = await system_service.pick_folder()
    except Exception as exc:  # noqa: BLE001 — superficie cualquier fallo del subproceso
        raise APIError("Error abriendo diálogo", status_code=500) from exc
    return ok({"path": path})
