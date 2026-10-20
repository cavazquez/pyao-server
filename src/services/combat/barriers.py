"""Absorción pura, compartida por todas las fuentes de daño al jugador."""

import time
from collections.abc import Mapping


def clear_barrier() -> dict[str, str]:
    """Devuelve el estado disipado sin capacidad residual.

    Returns:
        Campos persistibles de una barrera agotada.
    """
    return {"barrier_capacity": "0", "barrier_until": "0", "barrier_types": ""}


def absorb_damage(
    stats: Mapping[str, str], damage: int, kind: str, now: float | None = None
) -> tuple[int, dict[str, str]]:
    """Consume sólo el daño admitido y nunca produce capacidad negativa.

    Returns:
        Daño restante y cambios para el mismo EXEC que modifica el HP.
    """
    now = time.time() if now is None else now
    capacity = min(10000, max(0, int(stats.get("barrier_capacity", 0))))
    if float(stats.get("barrier_until", 0)) <= now or not capacity:
        return max(0, damage), clear_barrier() if stats.get(
            "barrier_until", "0"
        ) != "0" or capacity else {}
    if damage <= 0 or kind not in stats.get("barrier_types", "").split(","):
        return max(0, damage), {}
    absorbed = min(damage, capacity)
    remaining = capacity - absorbed
    return damage - absorbed, {"barrier_capacity": str(remaining)} if remaining else clear_barrier()
