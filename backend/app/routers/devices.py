"""Router para el planificador de dispositivos VRAM-aware (dry-run).

Endpoint:
    POST /api/devices/plan-preview — calcula el plan de dispositivos sin persistir nada.

Ubicación elegida: router independiente `devices.py` (en lugar de añadirlo a system.py)
porque el dominio es distinto: system.py agrupa operaciones del sistema operativo (hardware,
modelos, provider, reinicio) mientras que este router es exclusivamente del planner de VRAM.
Registrar un router separado también facilita añadir más endpoints del planner en el futuro
(p. ej. historial, comparativa de planes) sin saturar system.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.responses import ok
from app.deps.auth import require_auth
from app.services.rag.device_planner import _vram_total_mib, plan_devices


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class PlanPreviewRequest(BaseModel):
    """Cuerpo del dry-run del planificador de dispositivos.

    Ambos campos son opcionales; si no se envían se usan los valores por defecto
    equivalentes al comportamiento de arranque sin configuración explícita.
    """
    # Preset de prioridad: "search" prioriza latencia de consulta (LLM en GPU),
    # "ingest" prioriza velocidad de indexación (embeddings/whisper/ocr en GPU).
    processingPriority: str = "search"

    # Overrides por componente: "auto" | "gpu" | "cpu".
    # Solo se necesita incluir los que difieren del comportamiento automático.
    deviceOverrides: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/devices",
    tags=["devices"],
    dependencies=[Depends(require_auth)],
)


@router.post("/plan-preview")
async def plan_preview(body: PlanPreviewRequest):
    """Calcula el plan de dispositivos para la configuración recibida sin persistir nada.

    Usa la VRAM detectada en tiempo real (nvidia-smi) para determinar qué modelos
    propios (embeddings, reranker, whisper, ocr) caben en GPU con los parámetros dados.

    Respuesta incluye:
    - devices:                  mapa componente → "cpu" | "cuda"
    - ollama_gpu_overhead_bytes: bytes que Ollama debe reservar para el LLM
    - feasible:                 False si algún override "gpu" no cabe en el presupuesto
    - vram_total_mib:           VRAM total detectada (0 = sin GPU)
    - budget_mib:               presupuesto disponible (vram_total - colchón)
    - gpu_used_mib:             suma de costes de modelos propios que sí caben en GPU
    - overflow:                 lista de componentes forzados a GPU que no caben

    Este endpoint es un dry-run: no modifica runtime_settings ni Mongo.
    """
    vram = _vram_total_mib()
    resultado = plan_devices(
        priority=body.processingPriority,
        overrides=body.deviceOverrides,
        vram_total_mib=vram,
    )
    return ok(resultado)
