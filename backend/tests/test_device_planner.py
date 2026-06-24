"""Tests unitarios del planificador de dispositivos VRAM-aware.

Escenarios sintéticos con distintos tamaños de VRAM y presets de prioridad.
No requieren GPU real: se pasa vram_total_mib directamente a plan_devices().
"""

import pytest

from app.services.rag.device_planner import (
    _ONNX_COMPONENTS,
    _OVERHEAD_FRACTION,
    _OVERHEAD_MIN_MIB,
    _VRAM_COSTS_MIB,
    invalidate_cache,
    plan_devices,
)

# Compatibilidad con tests existentes que usaban la constante eliminada.
_LLM_COST_MIB = _VRAM_COSTS_MIB["llm"]["cost_mib"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _presupuesto(vram_mib: int) -> int:
    """Calcula el presupuesto esperado igual que lo hace plan_devices."""
    colchon = max(int(vram_mib * _OVERHEAD_FRACTION), _OVERHEAD_MIN_MIB)
    return vram_mib - colchon


def _cost(comp: str) -> int:
    return _VRAM_COSTS_MIB[comp]["cost_mib"]


# ---------------------------------------------------------------------------
# Sin GPU (vram_total_mib == 0)
# ---------------------------------------------------------------------------

class TestSinGPU:
    def test_todo_cpu(self):
        result = plan_devices("search", {}, 0)
        assert all(v == "cpu" for v in result["devices"].values()), (
            "Sin GPU todos los componentes deben ir a CPU"
        )

    def test_overhead_cero(self):
        result = plan_devices("search", {}, 0)
        assert result["ollama_gpu_overhead_bytes"] == 0

    def test_ingest_priority_también_todo_cpu(self):
        result = plan_devices("ingest", {}, 0)
        assert all(v == "cpu" for v in result["devices"].values())


# ---------------------------------------------------------------------------
# 4096 MiB (GTX 1650 de referencia)
# ---------------------------------------------------------------------------

class TestVRAM4GB:
    """Con 4 GB (presupuesto 4096 - 512 = 3584 MiB) NO caben e5 (2620) y el LLM (~3000)
    a la vez. En preset 'search' el LLM tiene prioridad y reserva la GPU, así que TODOS
    los modelos propios caen a CPU (es lo correcto: consultas rápidas con el LLM en GPU)."""

    VRAM = 4096

    def test_search_priority_embeddings_cede_al_llm(self):
        """Preset 'search' en 4 GB: el LLM (~3000 MiB) reserva la GPU primero, así que el
        e5 (2620 MiB, el gran consumidor) NO cabe → va a CPU. Esta es la regresión clave:
        antes el planner metía embeddings+reranker en GPU y dejaba el LLM en CPU."""
        result = plan_devices("search", {}, self.VRAM)
        devices = result["devices"]
        assert devices["embeddings"] == "cpu", (
            f"En 'search' con 4 GB el e5 debe ceder la GPU al LLM; devices={devices}"
        )
        assert devices["reranker"] == "cpu", (
            f"En 'search' con 4 GB el reranker no cabe junto al LLM; devices={devices}"
        )

    def test_search_priority_deja_sitio_al_llm(self):
        """Invariante central del preset 'search': tras colocar los modelos propios, debe
        quedar VRAM suficiente para el LLM en GPU (presupuesto - overhead ≥ coste del LLM).
        Modelos pequeños (whisper/ocr) pueden ocupar el hueco sobrante sin romperlo."""
        presupuesto = _presupuesto(self.VRAM)
        result = plan_devices("search", {}, self.VRAM)
        overhead_mib = result["ollama_gpu_overhead_bytes"] // (1024 * 1024)
        assert presupuesto - overhead_mib >= _LLM_COST_MIB, (
            f"El LLM debe caber en GPU: presupuesto {presupuesto} - overhead {overhead_mib} "
            f"< coste LLM {_LLM_COST_MIB}"
        )

    def test_ingest_priority_embeddings_primero(self):
        """Preset 'ingest': embeddings (ingest, 2620 MiB) primero → cabe en 3584.
        Luego Whisper (450) y OCR (150) también cabrían: 3584 - 2620 = 964 ≥ 450+150.
        Reranker (query) va al final y puede no caber según el resto."""
        result = plan_devices("ingest", {}, self.VRAM)
        devices = result["devices"]
        assert devices["embeddings"] == "cuda", (
            "En preset 'ingest' con 4 GB los embeddings deben ir a GPU"
        )

    def test_ingest_overhead_refleja_lo_que_va_a_gpu(self):
        result = plan_devices("ingest", {}, self.VRAM)
        devices = result["devices"]
        # Overhead cuenta solo componentes ONNX (no llm/vision, que gestiona Ollama)
        gpu_cost_mib = sum(
            _cost(c) for c, d in devices.items() if d == "cuda" and c in _ONNX_COMPONENTS
        )
        expected_bytes = gpu_cost_mib * 1024 * 1024
        assert result["ollama_gpu_overhead_bytes"] == expected_bytes


# ---------------------------------------------------------------------------
# 8192 MiB
# ---------------------------------------------------------------------------

class TestVRAM8GB:
    """Con 8 GB el presupuesto es 8192 - 819 = 7373 MiB (10% de colchón > 512).
    Todos los modelos ONNX (2620+800+450+150 = 4020 MiB) deben caber en cualquier preset."""

    VRAM = 8192

    def test_search_todo_onnx_cabe_en_gpu(self):
        """Con 8 GB los 4 componentes ONNX caben en GPU en 'search'.
        Vision (3500 MiB) no cabe porque llm/reranker/embeddings/whisper/ocr ya
        consumieron el presupuesto antes que ella en el orden de prioridad."""
        result = plan_devices("search", {}, self.VRAM)
        devices = result["devices"]
        for comp in _ONNX_COMPONENTS:
            assert devices[comp] == "cuda", (
                f"Con 8 GB el componente ONNX {comp} debe ir a GPU; devices={devices}"
            )

    def test_search_llm_en_gpu(self):
        """En 'search' con 8 GB el LLM (prioridad máxima) debe ir a GPU."""
        result = plan_devices("search", {}, self.VRAM)
        assert result["devices"]["llm"] == "cuda"

    def test_ingest_embeddings_vision_caben_en_gpu(self):
        """En 'ingest' con 8 GB embeddings y vision (alta prioridad) van a GPU."""
        result = plan_devices("ingest", {}, self.VRAM)
        devices = result["devices"]
        assert devices["embeddings"] == "cuda"
        assert devices["vision"] == "cuda"

    def test_overhead_solo_onnx(self):
        """El overhead solo cuenta componentes ONNX (no llm/vision)."""
        result = plan_devices("search", {}, self.VRAM)
        devices = result["devices"]
        onnx_gpu_mib = sum(
            _cost(c) for c, d in devices.items()
            if d == "cuda" and c in _ONNX_COMPONENTS
        )
        expected_bytes = onnx_gpu_mib * 1024 * 1024
        assert result["ollama_gpu_overhead_bytes"] == expected_bytes


# ---------------------------------------------------------------------------
# 12288 MiB (12 GB)
# ---------------------------------------------------------------------------

class TestVRAM12GB:
    """Con 12 GB no hay conflicto: todo cabe y el preset es irrelevante."""

    VRAM = 12288

    def test_todo_gpu_search(self):
        result = plan_devices("search", {}, self.VRAM)
        assert all(v == "cuda" for v in result["devices"].values())

    def test_todo_gpu_ingest(self):
        result = plan_devices("ingest", {}, self.VRAM)
        assert all(v == "cuda" for v in result["devices"].values())

    def test_overhead_correcto(self):
        """En 12 GB todo va a cuda; el overhead es la suma de los 4 componentes ONNX."""
        result = plan_devices("search", {}, self.VRAM)
        onnx_gpu_mib = sum(_cost(c) for c in _ONNX_COMPONENTS)
        assert result["ollama_gpu_overhead_bytes"] == onnx_gpu_mib * 1024 * 1024


# ---------------------------------------------------------------------------
# Overrides manuales
# ---------------------------------------------------------------------------

class TestOverrides:
    VRAM = 8192  # suficiente para que sin overrides todo fuera a GPU

    def test_override_cpu_fuerza_componente_a_cpu(self):
        """Aunque haya VRAM suficiente, un override "cpu" lo mantiene en CPU."""
        result = plan_devices("search", {"embeddings": "cpu"}, self.VRAM)
        assert result["devices"]["embeddings"] == "cpu"

    def test_override_gpu_fuerza_componente_a_gpu(self):
        """Con 0 MiB de VRAM los overrides "gpu" no se pueden satisfacer, pero con VRAM
        suficiente un override "gpu" explícito funciona aunque sea fase de baja prioridad."""
        result = plan_devices("search", {"ocr": "gpu"}, self.VRAM)
        assert result["devices"]["ocr"] == "cuda"

    def test_override_cpu_no_cuenta_en_overhead(self):
        """Un componente forzado a CPU no debe sumar al overhead de Ollama."""
        sin_override = plan_devices("search", {}, self.VRAM)
        con_override = plan_devices("search", {"embeddings": "cpu"}, self.VRAM)

        coste_emb = _cost("embeddings") * 1024 * 1024
        # El overhead con el override debe ser menor (no cuenta el e5)
        diff = sin_override["ollama_gpu_overhead_bytes"] - con_override["ollama_gpu_overhead_bytes"]
        assert diff == coste_emb, (
            f"El override cpu de embeddings debe reducir el overhead en {coste_emb} bytes"
        )

    def test_override_auto_equivale_a_sin_override(self):
        """Un override "auto" es lo mismo que no especificar override."""
        sin_override = plan_devices("search", {}, self.VRAM)
        con_auto = plan_devices("search", {"reranker": "auto"}, self.VRAM)
        assert sin_override["devices"] == con_auto["devices"]
        assert sin_override["ollama_gpu_overhead_bytes"] == con_auto["ollama_gpu_overhead_bytes"]

    def test_override_mix_cpu_y_gpu(self):
        """Overrides mixtos: reranker a CPU, embeddings a GPU."""
        result = plan_devices("search", {"reranker": "cpu", "embeddings": "gpu"}, self.VRAM)
        assert result["devices"]["reranker"] == "cpu"
        assert result["devices"]["embeddings"] == "cuda"

    def test_override_gpu_sin_vram_no_fuerza_cuda(self):
        """Con 0 MiB de VRAM, incluso el override "gpu" devuelve cpu (sin GPU física)."""
        # El planner hace early-return si vram == 0, por lo que los overrides se ignoran.
        result = plan_devices("search", {"reranker": "gpu"}, 0)
        assert result["devices"]["reranker"] == "cpu"


# ---------------------------------------------------------------------------
# Propiedades del overhead
# ---------------------------------------------------------------------------

class TestOverheadPropiedades:
    def test_overhead_es_suma_de_costes_onnx_gpu(self):
        """overhead_bytes es la suma de costes ONNX (MiB→bytes) asignados a GPU.
        LLM y vision no cuentan aunque estén en cuda."""
        vram = 8192
        result = plan_devices("search", {}, vram)
        devices = result["devices"]
        onnx_gpu_bytes = sum(
            _cost(c) * 1024 * 1024
            for c, d in devices.items()
            if d == "cuda" and c in _ONNX_COMPONENTS
        )
        assert result["ollama_gpu_overhead_bytes"] == onnx_gpu_bytes

    def test_presupuesto_no_excedido(self):
        """El coste total GPU nunca debe superar el presupuesto (vram - colchón)."""
        for vram in [4096, 6144, 8192, 12288]:
            for priority in ["search", "ingest"]:
                result = plan_devices(priority, {}, vram)
                gpu_cost_mib = sum(
                    _cost(c) for c, d in result["devices"].items() if d == "cuda"
                )
                presupuesto = _presupuesto(vram)
                assert gpu_cost_mib <= presupuesto, (
                    f"vram={vram}, priority={priority}: "
                    f"coste GPU {gpu_cost_mib} > presupuesto {presupuesto}"
                )


# ---------------------------------------------------------------------------
# Feasibilidad y overflow (§11.2 del spec)
# ---------------------------------------------------------------------------

class TestFeasibilidad:
    """Verifica los campos feasible, vram_total_mib, budget_mib, gpu_used_mib y overflow."""

    VRAM = 4096  # GTX 1650 de referencia; presupuesto = 4096 - 512 = 3584 MiB

    def test_sin_overrides_siempre_feasible(self):
        """Sin overrides el greedy nunca supera el presupuesto → siempre feasible."""
        for vram in [4096, 8192, 12288]:
            for priority in ["search", "ingest"]:
                result = plan_devices(priority, {}, vram)
                assert result["feasible"] is True, (
                    f"Sin overrides debe ser feasible (vram={vram}, priority={priority})"
                )
                assert result["overflow"] == [], (
                    f"Sin overrides overflow debe estar vacío (vram={vram})"
                )

    def test_sin_gpu_feasible_y_campos_cero(self):
        """Sin GPU todos los campos de feasibilidad tienen valores neutros."""
        result = plan_devices("search", {}, 0)
        assert result["feasible"] is True
        assert result["vram_total_mib"] == 0
        assert result["budget_mib"] == 0
        assert result["gpu_used_mib"] == 0
        assert result["overflow"] == []

    def test_vram_total_y_budget_correctos(self):
        """vram_total_mib y budget_mib deben coincidir con los valores esperados."""
        result = plan_devices("search", {}, self.VRAM)
        assert result["vram_total_mib"] == self.VRAM
        assert result["budget_mib"] == _presupuesto(self.VRAM)

    def test_overrides_que_caben_son_feasible(self):
        """Forzar embeddings (2620) + reranker (800) = 3420 ≤ 3584 → feasible True.

        gpu_used_mib puede ser mayor que 3420 porque los componentes "auto" que caben
        en el presupuesto restante (164 MiB) también suman (p. ej. ocr=150 MiB → 3570).
        """
        # 2620 + 800 = 3420 ≤ 3584 (presupuesto de 4096 MiB)
        result = plan_devices("search", {"embeddings": "gpu", "reranker": "gpu"}, self.VRAM)
        assert result["feasible"] is True, (
            f"embeddings+reranker (3420 MiB) deben caber en el presupuesto {_presupuesto(self.VRAM)} MiB"
        )
        assert result["overflow"] == []
        # gpu_used_mib es la suma de TODOS los componentes propios en cuda (incluidos los
        # componentes "auto" que el greedy colocó en GPU con el presupuesto restante).
        gpu_used_esperado = sum(
            _cost(c) for c, d in result["devices"].items() if d == "cuda"
        )
        assert result["gpu_used_mib"] == gpu_used_esperado, (
            f"gpu_used_mib debe coincidir con la suma de costes en cuda: "
            f"esperado {gpu_used_esperado}, obtenido {result['gpu_used_mib']}"
        )

    def test_overrides_que_no_caben_son_infeasible(self):
        """Forzar embeddings+reranker+whisper+ocr supera el presupuesto de 4096 MiB.

        2620 + 800 + 450 + 150 = 4020 > 3584 → feasible False, overflow no vacío.
        """
        overrides = {
            "embeddings": "gpu",
            "reranker": "gpu",
            "whisper": "gpu",
            "ocr": "gpu",
        }
        result = plan_devices("search", overrides, self.VRAM)
        assert result["feasible"] is False, (
            "Forzar todos a GPU en 4 GB debe resultar infeasible "
            f"(coste total {sum(_cost(c) for c in overrides)} MiB > {_presupuesto(self.VRAM)} MiB)"
        )
        assert len(result["overflow"]) > 0, "Debe haber al menos un componente en overflow"

    def test_overflow_solo_contiene_los_que_no_caben(self):
        """Los componentes en overflow son los que hicieron superar el presupuesto.

        Con embeddings (2620) + reranker (800) = 3420 ≤ 3584: los dos caben.
        Añadir whisper (450): 3420 + 450 = 3870 > 3584 → whisper va a overflow.
        """
        overrides = {"embeddings": "gpu", "reranker": "gpu", "whisper": "gpu"}
        result = plan_devices("search", overrides, self.VRAM)
        assert result["feasible"] is False
        assert "whisper" in result["overflow"], (
            f"whisper debería estar en overflow; overflow={result['overflow']}"
        )
        # embeddings y reranker caben → no deben estar en overflow
        assert "embeddings" not in result["overflow"]
        assert "reranker" not in result["overflow"]

    def test_devices_respetan_override_aunque_sea_infeasible(self):
        """Aunque el plan sea infeasible, devices siempre refleja la petición del usuario.

        El componente en overflow aparece como "cuda" en devices (la UI usa feasible/overflow
        para avisar y bloquear "Aplicar", no para silenciosamente mover el device a CPU).
        """
        overrides = {"embeddings": "gpu", "reranker": "gpu", "whisper": "gpu"}
        result = plan_devices("search", overrides, self.VRAM)
        assert result["devices"]["whisper"] == "cuda", (
            "El componente en overflow debe seguir siendo 'cuda' en devices "
            "(la UI bloquea; el planner no cambia la petición del usuario)"
        )

    def test_gpu_used_mib_excluye_overflow(self):
        """gpu_used_mib solo cuenta los componentes que SÍ caben (no los del overflow).

        Con embeddings+reranker forzados (3420 MiB) y whisper forzado (overflow) en 4 GB:
        gpu_used_mib = suma de los "cuda" que NO están en overflow. Ocr (auto, 150 MiB)
        puede o no estar en cuda según el presupuesto restante; lo calculamos dinámicamente.
        """
        overrides = {"embeddings": "gpu", "reranker": "gpu", "whisper": "gpu"}
        result = plan_devices("search", overrides, self.VRAM)
        # Solo los componentes en cuda que no están en overflow cuentan.
        overflow = set(result["overflow"])
        esperado = sum(
            _cost(c) for c, d in result["devices"].items() if d == "cuda" and c not in overflow
        )
        assert result["gpu_used_mib"] == esperado, (
            f"gpu_used_mib debe excluir el overflow; esperado {esperado}, "
            f"obtenido {result['gpu_used_mib']}"
        )

    def test_feasible_en_8gb_con_todos_forzados(self):
        """En 8 GB (presupuesto 7373 MiB) forzar todos a GPU debe ser feasible.

        Coste total propio: 2620 + 800 + 450 + 150 = 4020 MiB ≤ 7373 MiB.
        """
        overrides = {
            "embeddings": "gpu",
            "reranker": "gpu",
            "whisper": "gpu",
            "ocr": "gpu",
        }
        result = plan_devices("search", overrides, 8192)
        assert result["feasible"] is True, (
            "En 8 GB todos los componentes deben caber sin overflow"
        )
        assert result["overflow"] == []
        assert result["gpu_used_mib"] == sum(_cost(c) for c in overrides)


# ---------------------------------------------------------------------------
# LLM y Vision como componentes de pleno derecho
# ---------------------------------------------------------------------------

class TestLlmVisionComponents:
    """Verifica que llm y vision aparecen en devices y se planifican correctamente."""

    def test_sin_gpu_llm_y_vision_cpu(self):
        result = plan_devices("search", {}, 0)
        assert result["devices"]["llm"] == "cpu"
        assert result["devices"]["vision"] == "cpu"

    def test_devices_tiene_seis_componentes(self):
        """plan_devices siempre devuelve exactamente 6 componentes."""
        result = plan_devices("search", {}, 4096)
        expected_keys = {"embeddings", "reranker", "whisper", "ocr", "llm", "vision"}
        assert set(result["devices"].keys()) == expected_keys

    def test_search_priority_llm_alta_prioridad(self):
        """En 'search' el LLM (3000 MiB) tiene la máxima prioridad → va a GPU en 4 GB
        (presupuesto 3584 MiB) porque es el primero en la lista."""
        result = plan_devices("search", {}, 4096)
        assert result["devices"]["llm"] == "cuda", (
            "En 'search' con 4 GB el LLM debe ir a GPU (primera prioridad)"
        )

    def test_ingest_priority_vision_alta_prioridad(self):
        """En 'ingest' vision tiene alta prioridad (segunda tras embeddings)."""
        # Con 8 GB (budget 7373) embeddings (2620) + vision (3500) = 6120 ≤ 7373
        result = plan_devices("ingest", {}, 8192)
        assert result["devices"]["vision"] == "cuda", (
            "En 'ingest' con 8 GB vision debe ir a GPU"
        )

    def test_override_llm_cpu_fuerza_cpu(self):
        """Un override 'cpu' en llm lo fuerza a CPU aunque haya VRAM."""
        result = plan_devices("search", {"llm": "cpu"}, 8192)
        assert result["devices"]["llm"] == "cpu"

    def test_override_vision_gpu_fuerza_gpu(self):
        """Un override 'gpu' en vision con VRAM suficiente lo pone en cuda."""
        result = plan_devices("search", {"vision": "gpu"}, 8192)
        assert result["devices"]["vision"] == "cuda"

    def test_overhead_excluye_llm_y_vision(self):
        """El overhead de Ollama NUNCA incluye llm ni vision (los gestiona Ollama)."""
        # En 12 GB todo va a cuda; aun así el overhead excluye llm+vision
        result = plan_devices("search", {}, 12288)
        assert result["devices"]["llm"] == "cuda"
        assert result["devices"]["vision"] == "cuda"
        onnx_mib = sum(_cost(c) for c in _ONNX_COMPONENTS)
        assert result["ollama_gpu_overhead_bytes"] == onnx_mib * 1024 * 1024, (
            "overhead_bytes no debe incluir llm ni vision aunque estén en cuda"
        )

    def test_feasible_con_overrides_llm_vision(self):
        """Overrides de llm y vision en 12 GB deben ser feasible."""
        result = plan_devices("search", {"llm": "gpu", "vision": "gpu"}, 12288)
        assert result["feasible"] is True

    def test_overflow_vision_cuando_no_cabe(self):
        """Vision (3500 MiB) y llm (3000 MiB) forzados a GPU en 4 GB (presupuesto 3584)
        no caben juntos: total 6500 > 3584 → infeasible."""
        result = plan_devices("search", {"llm": "gpu", "vision": "gpu"}, 4096)
        assert result["feasible"] is False
        assert len(result["overflow"]) > 0
