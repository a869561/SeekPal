"""Tests del snapshot de progreso de ingesta (reconexion SSE).

El bug: al desconectar el SSE (cambio de pestana / F5) y reconectar, el cliente
recibia 409 y se quedaba en una barra indeterminada porque el progreso solo
vivia en el componente React y en la cola por-conexion. La solucion mantiene un
snapshot por fuente en el servidor (`_apply_event` sobre `_empty_snapshot`) que
el cliente recupera via GET .../ingest/progress.
"""

from __future__ import annotations

from app.routers.ingest import _apply_event, _empty_snapshot


def _reduce(events: list[dict]) -> dict:
    snap = _empty_snapshot()
    for ev in events:
        snap = _apply_event(snap, ev)
    return snap


def test_empty_snapshot_is_active_scanning():
    snap = _empty_snapshot()
    assert snap["active"] is True
    assert snap["phase"] == "scanning"
    assert snap["paused"] is False
    assert snap["scan"] == {"current": 0, "total": 0, "file": ""}


def test_scan_progress_updates_scan_block():
    snap = _reduce([{"type": "progress", "current": 5, "total": 20, "file": "a.pdf"}])
    assert snap["phase"] == "scanning"
    assert snap["scan"] == {"current": 5, "total": 20, "file": "a.pdf"}


def test_extracting_sets_phase_and_block():
    snap = _reduce([{"type": "extracting_progress", "current": 3, "total": 10, "file": "x.txt"}])
    assert snap["phase"] == "extracting"
    assert snap["extract"] == {"current": 3, "total": 10, "file": "x.txt"}


def test_embedding_start_then_progress():
    snap = _reduce([
        {"type": "extracting_progress", "current": 10, "total": 10, "file": "x.txt"},
        {"type": "embedding_start", "total": 10},
        {"type": "embedding_progress", "current": 4, "total": 12},
    ])
    assert snap["phase"] == "embedding"
    assert snap["extract"]["total"] == 10           # extract.total preservado
    assert snap["embed"] == {"current": 4, "total": 12}


def test_indexing_progress():
    snap = _reduce([{"type": "indexing_progress", "current": 7, "total": 15, "file": "y.md"}])
    assert snap["phase"] == "indexing"
    assert snap["index"] == {"current": 7, "total": 15, "file": "y.md"}


def test_pause_resume_toggles_flag_without_losing_phase():
    snap = _reduce([
        {"type": "indexing_progress", "current": 7, "total": 15, "file": "y.md"},
        {"type": "paused"},
    ])
    assert snap["paused"] is True
    assert snap["phase"] == "indexing"   # la fase subyacente se conserva
    snap = _apply_event(snap, {"type": "resumed"})
    assert snap["paused"] is False
    assert snap["phase"] == "indexing"


def test_done_marks_inactive():
    snap = _reduce([
        {"type": "indexing_progress", "current": 15, "total": 15, "file": "z.md"},
        {"type": "done"},
    ])
    assert snap["active"] is False
    assert snap["phase"] == "done"


def test_error_marks_inactive_with_message():
    snap = _reduce([{"type": "error", "message": "boom"}])
    assert snap["active"] is False
    assert snap["phase"] == "error"
    assert snap["error"] == "boom"


def test_cancelled_marks_inactive():
    snap = _reduce([{"type": "cancelled"}])
    assert snap["active"] is False
    assert snap["phase"] == "cancelled"


def test_full_lifecycle_snapshot_reconstructs_real_progress():
    """Simula la secuencia real y verifica que un cliente que reconecta a mitad
    de la fase de indexado obtendria el progreso correcto, no indeterminado."""
    snap = _reduce([
        {"type": "scanning"},
        {"type": "progress", "current": 68, "total": 68, "file": "last.pdf"},
        {"type": "extracting_progress", "current": 68, "total": 68, "file": "last.pdf"},
        {"type": "embedding_start", "total": 68},
        {"type": "embedding_progress", "current": 558, "total": 558},
        {"type": "indexing_progress", "current": 40, "total": 68, "file": "mid.pdf"},
    ])
    assert snap["active"] is True
    assert snap["phase"] == "indexing"
    assert snap["scan"]["total"] == 68
    assert snap["index"] == {"current": 40, "total": 68, "file": "mid.pdf"}
