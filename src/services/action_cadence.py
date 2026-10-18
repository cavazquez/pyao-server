"""Presupuestos monotónicos compartidos, independientes por jugador y acción."""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Literal

from src.config.config_manager import ConfigManager, config_manager

Action = Literal["walk", "attack", "cast", "work"]
DEFAULT_INTERVALS: dict[Action, float] = {"walk": 0.2, "attack": 0.5, "cast": 1.0, "work": 0.5}
PRUNE_SECONDS = 60.0


@dataclass
class Reservation:
    """Una ejecución en curso y el instante mínimo de la siguiente."""

    next_at: float
    busy: bool = True


class ActionCadence:
    """No cede control entre comprobar el plazo y reservar una ejecución."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        """El reloj inyectable permite verificar fronteras sin sleeps."""
        self.clock = clock
        self._reservations: dict[tuple[int, Action], Reservation] = {}
        self._prune_at = clock() + PRUNE_SECONDS

    def claim(self, user_id: int, action: Action) -> bool:
        """Reserva antes del primer await, incluso entre handlers distintos.

        Returns:
            False si hay otra ejecución en curso o el intervalo no terminó.
        """
        now = self.clock()
        if now >= self._prune_at:
            self._reservations = {
                key: state
                for key, state in self._reservations.items()
                if state.busy or state.next_at > now
            }
            self._prune_at = now + PRUNE_SECONDS
        key = user_id, action
        previous = self._reservations.get(key)
        if previous and (previous.busy or now < previous.next_at):
            return False
        interval = ConfigManager.as_float(
            config_manager.get(f"game.cadence.{action}_seconds", DEFAULT_INTERVALS[action]),
            DEFAULT_INTERVALS[action],
        )
        self._reservations[key] = Reservation(now + interval)
        return True

    def release(self, user_id: int, action: Action) -> None:
        """Libera el trabajo, conservando el plazo entre muerte y reconexión."""
        state = self._reservations.get((user_id, action))
        if state:
            state.busy = False
