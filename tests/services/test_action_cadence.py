"""Cadencia compartida: reloj controlado, reserva previa y aislamiento."""

import pytest

from src.services.action_cadence import ActionCadence


@pytest.mark.parametrize(("action", "interval"), [("walk", 0.2), ("attack", 0.5), ("cast", 1.0)])
def test_burst_boundary_inflight_and_independent_users(action, interval):
    """Una ejecución lenta bloquea incluso después del plazo, sin gastar otro permiso."""
    now = [100.0]
    cadence = ActionCadence(clock=lambda: now[0])
    assert cadence.claim(1, action)
    assert not any(cadence.claim(1, action) for _ in range(100))
    assert cadence.claim(2, action)
    now[0] += interval
    assert not cadence.claim(1, action)  # La primera ejecución aún está en curso.
    cadence.release(1, action)
    assert cadence.claim(1, action)
    cadence.release(1, action)
    now[0] += interval - 0.001
    assert not cadence.claim(1, action)
    now[0] += 0.001001
    assert cadence.claim(1, action)


def test_actions_are_independent_and_expired_entries_are_pruned():
    """Muerte/reconexión conservan el intervalo; la retención no crece para siempre."""
    now = [100.0]
    cadence = ActionCadence(clock=lambda: now[0])
    assert cadence.claim(1, "walk")
    assert cadence.claim(1, "cast")
    cadence.release(1, "walk")
    assert not cadence.claim(1, "walk")
    now[0] += 61.0
    assert cadence.claim(2, "attack")
    assert cadence.claim(1, "walk")
    assert not cadence.claim(1, "cast")  # No se poda el trabajo en curso.
