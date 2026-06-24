"""Planificador de dispositivos VRAM-aware para SeekPal.

Decide qué modelos ONNX/propios (embeddings, reranker, Whisper, OCR) corren en
GPU y cuáles en CPU, basándose en la VRAM disponible y la prioridad configurada.

El resultado se usa de dos formas:
  1. Cada servicio llama a `get_device_for(componente)` al arrancar para elegir su
     provider/device.
  2. `ollama_gpu_overhead_bytes` se exporta como variable de entorno `OLLAMA_GPU_OVERHEAD`
     ANTES de lanzar `ollama serve` en start.bat, para que Ollama sepa cuánta VRAM
     ya está reservada y encaje el LLM en el resto (desbordando a CPU solo lo que no quepa).

     TODO (start.bat): antes de `ollama serve`, añadir:
         set OLLAMA_GPU_OVERHEAD=<valor devuelto por plan_devices>
     El valor correcto se puede calcular arrancando Python y llamando a:
         python -c "from app.services.rag.device_planner import compute_overhead_bytes; print(compute_overhead_bytes())"

Fuente de los datos medidos:
  - GTX 1650, 4096 MiB total; base en reposo ~433 MiB.
  - intfloat/multilingual-e5-large (CUDAExecutionProvider): ~2620 MiB.
    (Gran parte es arena/workspace de ORT, no solo los pesos del modelo.)
  - jinaai/jina-reranker-v2-base-multilingual: ~570 MiB pesos; en GPU ONNX
    estimamos ~800 MiB (pesos + activaciones del cross-encoder). Sin medición real
    en este equipo (se forzó a CPU para evitar OOM), es estimación conservadora.
  - Whisper "small" en CTranslate2: ~400-500 MiB en GPU (estimación).
  - RapidOCR mobile: ~60 MiB (modelos PP-OCRv4 mobile ~15 MB c/u, workspace ligero).
  - RapidOCR server: ~250 MiB (modelos ~47+90 MB + workspace).
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("seekpal.device_planner")


# ---------------------------------------------------------------------------
# Tabla de costes VRAM conocidos (MiB) para modelos ONNX/propios.
# Origen: mediciones reales o estimaciones conservadoras documentadas arriba.
# ---------------------------------------------------------------------------

# Coste de VRAM en MiB por componente cuando corre en GPU.
# "fase" indica si el modelo se usa en ingesta ("ingest") o consulta ("query"):
#   - ingest: se carga durante la indexación de documentos.
#   - query:  se carga durante las consultas del usuario (alta prioridad en preset "search").
_VRAM_COSTS_MIB: dict[str, dict] = {
    "embeddings": {
        "cost_mib": 2620,   # MEDIDO: intfloat/multilingual-e5-large en ORT-CUDA (arena incluida)
        "phase": "ingest",  # en query solo embebe 1 frase; coste trivial en CPU
    },
    "reranker": {
        "cost_mib": 800,    # ESTIMADO: jina-reranker-v2 pesos ~570 MB + activaciones del cross-encoder
        "phase": "query",   # se ejecuta en cada consulta del usuario
    },
    "whisper": {
        "cost_mib": 450,    # ESTIMADO: faster-whisper "small" en CTranslate2 CUDA
        "phase": "ingest",
    },
    "ocr": {
        "cost_mib": 150,    # ESTIMADO: RapidOCR ONNX (mobile ~60 MiB, server ~250 MiB; usamos media)
        "phase": "ingest",
    },
    "llm": {
        "cost_mib": 3000,   # ESTIMADO: LLM 3-4B q4 + KV-cache a 8192 ctx
        "phase": "query",
    },
    "vision": {
        "cost_mib": 3500,   # ESTIMADO: VLM ~3B en GPU (qwen2.5vl:3b)
        "phase": "ingest",
    },
}

# Fallback para componentes no listados: estimación conservadora genérica.
_FALLBACK_COST_MIB = 1500

# Colchón de seguridad: el mayor de (10% de la VRAM total) o 512 MiB.
_OVERHEAD_FRACTION = 0.10
_OVERHEAD_MIN_MIB = 512

# Orden de prioridad explícito por preset (menor índice = más prioridad para GPU).
# Los seis componentes se planifican de forma greedy en este orden.
# "search": el LLM tiene la prioridad máxima (camino de consulta interactivo manda);
#   visión queda al final porque no se usa en consultas.
# "ingest": embeddings y visión primero (dominan el tiempo de indexación); LLM al final.
_PRIORITY_ORDER = {
    "search": ["llm", "reranker", "embeddings", "whisper", "ocr", "vision"],
    "ingest": ["embeddings", "vision", "whisper", "ocr", "reranker", "llm"],
}

# Componentes ONNX propios: los únicos que cuentan para OLLAMA_GPU_OVERHEAD.
# LLM y visión los gestiona Ollama directamente; no suman al overhead de start.bat.
_ONNX_COMPONENTS = frozenset({"embeddings", "reranker", "whisper", "ocr"})


def _vram_total_mib() -> int:
    """Detecta la VRAM total de la primera GPU NVIDIA mediante nvidia-smi.

    Devuelve 0 si no hay GPU o nvidia-smi no está disponible (sin GPU → todo CPU).
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return 0
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return 0
        # Tomamos la primera GPU (índice 0); en sistemas multi-GPU sería la primera.
        return int(lines[0])
    except Exception:
        return 0


def plan_devices(
    priority: str,
    overrides: dict[str, str],
    vram_total_mib: int,
) -> dict:
    """Calcula el device asignado a cada componente y el overhead para Ollama.

    Args:
        priority:      Preset de prioridad: "search" (default) o "ingest".
        overrides:     Dict por componente → "auto" | "gpu" | "cpu".
                       Los componentes no mencionados se tratan como "auto".
        vram_total_mib: VRAM total de la GPU en MiB (0 = sin GPU → todo CPU).

    Returns:
        {
            "devices": {
                "embeddings": "cpu" | "cuda",
                "reranker":   "cpu" | "cuda",
                "whisper":    "cpu" | "cuda",
                "ocr":        "cpu" | "cuda",
                "llm":        "cpu" | "cuda",
                "vision":     "cpu" | "cuda",
            },
            "ollama_gpu_overhead_bytes": int,
            # Campos de feasibilidad (§11.2 del spec):
            "feasible":          bool,         # False si algún override "gpu" no cabe.
            "vram_total_mib":    int,           # VRAM total detectada (0 = sin GPU).
            "budget_mib":        int,           # presupuesto = vram_total - colchón.
            "gpu_used_mib":      int,           # suma de costes ONNX propios en cuda que SÍ caben.
            "overflow":          list[str],     # componentes forzados a "gpu" que NO caben en el presupuesto.
        }

    Lógica (ver §4 del diseño):
      1. Si vram_total == 0 → todo CPU, overhead 0.
      2. Calcular presupuesto B = vram_total - max(vram_total*10%, 512 MiB).
      3. Aplicar overrides fijos ("gpu"/"cpu") primero; descontar su coste del presupuesto.
      4. Construir la lista de candidatos a GPU en orden de prioridad (_PRIORITY_ORDER),
         con los 6 componentes (incluidos llm y vision):
           "search" → llm, reranker, embeddings, whisper, ocr, vision.
           "ingest" → embeddings, vision, whisper, ocr, reranker, llm.
      5. Greedy: recorrer en orden reservando GPU mientras quepa. Cada componente recibe
         un device real (cuda/cpu); no hay componentes "fantasma" de solo presupuesto.
      6. overhead = suma de costes (en bytes) de los componentes ONNX propios en cuda
         (embeddings/reranker/whisper/ocr). LLM y visión los gestiona Ollama directamente
         y NO se incluyen en este overhead (start.bat los descuenta por su cuenta).
    """
    componentes = list(_VRAM_COSTS_MIB.keys())

    # Sin GPU → todo CPU inmediatamente.
    if vram_total_mib <= 0:
        return {
            "devices": {c: "cpu" for c in componentes},
            "ollama_gpu_overhead_bytes": 0,
            # Campos de feasibilidad (§11.2 del spec).
            "feasible": True,
            "vram_total_mib": 0,
            "budget_mib": 0,
            "gpu_used_mib": 0,
            "overflow": [],
        }

    # Presupuesto disponible en MiB.
    colchon = max(int(vram_total_mib * _OVERHEAD_FRACTION), _OVERHEAD_MIN_MIB)
    presupuesto_mib = vram_total_mib - colchon

    devices: dict[str, str] = {}
    gpu_cost_mib = 0  # coste acumulado de los modelos propios asignados a GPU

    # Paso 1: resolver overrides fijos.
    # Los overrides "gpu" se procesan distinguiendo si caben o no en el presupuesto
    # para calcular feasibilidad. En `devices` se respeta la petición del usuario
    # (siempre "cuda" si pidió "gpu"), aunque el plan resulte infeasible — la UI
    # usará `feasible`/`overflow` para avisar y bloquear "Aplicar".
    autos: list[str] = []
    overflow: list[str] = []         # componentes forzados a GPU que no caben
    presupuesto_restante_override = presupuesto_mib  # para detectar overflow en orden

    # Primero pasamos los overrides forzados a "gpu" y contamos su coste acumulado.
    forced_gpu: list[tuple[str, int]] = []  # (componente, coste) forzados a GPU
    for comp in componentes:
        override = overrides.get(comp, "auto")
        cost = _VRAM_COSTS_MIB.get(comp, {}).get("cost_mib", _FALLBACK_COST_MIB)
        if override == "gpu":
            forced_gpu.append((comp, cost))
        elif override == "cpu":
            devices[comp] = "cpu"
        else:
            autos.append(comp)

    # Calcular feasibilidad de los overrides "gpu": sumar en orden de llegada y
    # detectar cuáles provocan que se supere el presupuesto.
    gpu_cost_mib_override = 0
    for comp, cost in forced_gpu:
        devices[comp] = "cuda"  # respetar la petición del usuario siempre
        if gpu_cost_mib_override + cost <= presupuesto_mib:
            gpu_cost_mib_override += cost
        else:
            # Este componente (y los siguientes) ya no caben → overflow.
            overflow.append(comp)
        gpu_cost_mib += cost  # en el overhead contamos todos los que van a GPU

    # Presupuesto restante para los componentes "auto".
    restante_mib = presupuesto_mib - gpu_cost_mib_override

    # Paso 2: construir la lista de candidatos a GPU en orden de prioridad.
    # Los 6 componentes se ordenan por _PRIORITY_ORDER; todos reciben un device real.
    order = _PRIORITY_ORDER.get(priority, _PRIORITY_ORDER["search"])
    walk: list[tuple[str, int]] = [
        (comp, _VRAM_COSTS_MIB.get(comp, {}).get("cost_mib", _FALLBACK_COST_MIB))
        for comp in autos
    ]

    def _rank(item: tuple[str, int]) -> int:
        name = item[0]
        return order.index(name) if name in order else len(order)

    walk.sort(key=_rank)

    # Paso 3: greedy — recorrer en orden, reservando GPU mientras quepa.
    for name, cost in walk:
        if cost <= restante_mib:
            restante_mib -= cost
            devices[name] = "cuda"
            gpu_cost_mib += cost
            logger.debug("Planner: %s → cuda (%.0f MiB, restante %.0f MiB)", name, cost, restante_mib)
        else:
            devices[name] = "cpu"
            logger.debug("Planner: %s → cpu (coste %.0f MiB > restante %.0f MiB)", name, cost, restante_mib)

    # El overhead de Ollama es el coste (en bytes) de los modelos ONNX propios en GPU.
    # LLM y visión los gestiona Ollama directamente; no suman aquí.
    # Incluye los forzados por override aunque haya overflow — lo que está en "cuda"
    # físicamente reserva VRAM, aunque el plan resulte infeasible.
    overhead_bytes = sum(
        _VRAM_COSTS_MIB[c]["cost_mib"]
        for c, d in devices.items()
        if d == "cuda" and c in _ONNX_COMPONENTS
    ) * 1024 * 1024

    # Feasibilidad: True si no hay componentes forzados a GPU que no quepan.
    feasible = len(overflow) == 0

    # gpu_used_mib: solo los componentes ONNX que quedaron en cuda y NO están en overflow.
    # Refleja la VRAM reservada por los modelos propios que sí caben en el presupuesto.
    gpu_used_mib = sum(
        _VRAM_COSTS_MIB.get(c, {}).get("cost_mib", _FALLBACK_COST_MIB)
        for c, d in devices.items()
        if d == "cuda" and c not in overflow and c in _ONNX_COMPONENTS
    )

    logger.info(
        "Planner: VRAM %d MiB, prioridad=%s → %s | overhead Ollama %.0f MiB | feasible=%s overflow=%s",
        vram_total_mib,
        priority,
        devices,
        gpu_cost_mib,
        feasible,
        overflow,
    )

    return {
        "devices": devices,
        "ollama_gpu_overhead_bytes": overhead_bytes,
        # Campos de feasibilidad (§11.2 del spec).
        "feasible": feasible,
        "vram_total_mib": vram_total_mib,
        "budget_mib": presupuesto_mib,
        "gpu_used_mib": gpu_used_mib,
        "overflow": overflow,
    }


# ---------------------------------------------------------------------------
# Plan cacheado: se calcula una vez al arrancar y se reutiliza en cada servicio.
# ---------------------------------------------------------------------------

_cached_plan: dict | None = None


def _get_plan() -> dict:
    """Devuelve el plan cacheado (se calcula la primera vez que se llama).

    Lee priority y overrides de runtime_settings para reflejar la configuración
    guardada en Mongo por el usuario. Si runtime_settings aún no se ha cargado
    (arranque muy temprano o tests), usa los defaults.
    """
    global _cached_plan
    if _cached_plan is not None:
        return _cached_plan

    from app.core import runtime_settings

    priority: str = runtime_settings.get("processingPriority", "search")
    overrides: dict = runtime_settings.get("deviceOverrides", {}) or {}
    vram = _vram_total_mib()

    _cached_plan = plan_devices(priority, overrides, vram)
    return _cached_plan


def get_device_for(component: str) -> str:
    """Devuelve el device asignado a un componente por el planificador.

    Args:
        component: "embeddings" | "reranker" | "whisper" | "ocr" | "llm" | "vision".

    Returns:
        "cuda" si el componente debe correr en GPU, "cpu" en caso contrario.
        Si el componente no está en el plan (desconocido), devuelve "cpu" como
        fallback seguro.
    """
    plan = _get_plan()
    return plan["devices"].get(component, "cpu")


def compute_overhead_bytes() -> int:
    """Devuelve los bytes de VRAM que ocupan los modelos ONNX/propios asignados a GPU.

    Este valor debe exportarse como `OLLAMA_GPU_OVERHEAD` en start.bat antes de
    lanzar `ollama serve`, para que Ollama reserve solo la VRAM que realmente sobra
    para el LLM y evite over-commit.

    TODO (start.bat): añadir antes de `ollama serve`:
        for /f %%i in ('python -c "from app.services.rag.device_planner import compute_overhead_bytes; print(compute_overhead_bytes())"') do set OLLAMA_GPU_OVERHEAD=%%i
    """
    return _get_plan()["ollama_gpu_overhead_bytes"]


def invalidate_cache() -> None:
    """Invalida el plan cacheado. Útil en tests o si los settings cambian en memoria."""
    global _cached_plan
    _cached_plan = None
