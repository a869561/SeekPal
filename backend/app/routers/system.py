from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from app.core.responses import APIError, ok
from app.deps.auth import require_auth
from app.services import system_service


router = APIRouter(prefix="/api/system", tags=["system"], dependencies=[Depends(require_auth)])


@router.get("/folder-picker")
async def folder_picker():
    try:
        path = await system_service.pick_folder()
    except Exception as exc:
        raise APIError("Error abriendo diálogo", status_code=500) from exc
    return ok({"path": path})


@router.get("/hardware")
async def hardware_info():
    """Devuelve componentes detectados (CPU, RAM, GPUs) y provider de embeddings activo."""
    from app.core.database import get_embedding_service

    hw = await system_service.detect_hardware()

    try:
        svc = get_embedding_service()
        active_provider = getattr(svc, "active_provider", "CPUExecutionProvider")
    except RuntimeError:
        active_provider = "CPUExecutionProvider"

    _PROVIDER_LABEL = {
        "CUDAExecutionProvider": "Gráficos (NVIDIA)",
        "DirectMLExecutionProvider": "Gráficos (AMD/Intel)",
        "CPUExecutionProvider": "Procesador",
    }
    active_label = _PROVIDER_LABEL.get(active_provider, "Procesador")

    # Determinar qué índice de GPU está activo (para el frontend "Gráficos 1")
    gpu_index: int | None = None
    if active_provider != "CPUExecutionProvider" and hw["gpus"]:
        gpu_index = 0  # el primero de la lista WMI es el que ONNX usa

    # Recomendar paquete si hay GPUs pero se está usando CPU
    recommendation: dict | None = None
    if active_provider == "CPUExecutionProvider" and hw["gpus"]:
        pkg = system_service._recommend_package(hw["gpus"])
        if pkg:
            recommendation = {"package": pkg}

    return ok({
        "cpu": hw["cpu"],
        "ram_gb": hw["ram_gb"],
        "gpus": hw["gpus"],
        "active_provider": active_provider,
        "active_label": active_label,
        "active_gpu_index": gpu_index,  # None si usa CPU
        "recommendation": recommendation,
    })


@router.get("/install-status")
async def install_status():
    """Estado de la instalación de aceleración GPU en progreso."""
    return ok(system_service.get_install_status())


@router.post("/enable-gpu")
async def enable_gpu(background_tasks: BackgroundTasks):
    """Instala el paquete onnxruntime adecuado para la GPU detectada y reinicia SeekPal."""
    current = system_service.get_install_status()
    if current["status"] == "installing":
        raise APIError("Ya hay una instalación en progreso", status_code=409)

    hw = await system_service.detect_hardware()
    pkg = system_service._recommend_package(hw["gpus"])
    if pkg is None:
        raise APIError("No se han detectado gráficos compatibles", status_code=404)

    background_tasks.add_task(system_service.install_gpu_package, pkg)
    return ok({"status": "installing", "package": pkg})


@router.post("/restart")
async def restart(force: bool = False):
    """Reinicia SeekPal (aplica cambios de configuración).

    Si hay ingestas activas y force=False, devuelve 409 para que el frontend
    muestre confirmación. Con force=True reinicia aunque haya ingestas.
    """
    from app.services.scanner_service import _pause_events

    # _pause_events tiene una entrada por cada ingesta activa o pausada.
    # cleanup_ingest() la elimina al terminar, así que si hay entradas → hay ingesta.
    active_ingestions = list(_pause_events.keys())

    if active_ingestions and not force:
        return JSONResponse(status_code=409, content={
            "success": False,
            "message": "Hay archivos indexándose",
            "data": {"ingestions": active_ingestions},
        })

    system_service.restart_app()
    return ok({"status": "restarting"})
