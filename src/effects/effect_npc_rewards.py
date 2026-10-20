"""Reintenta muertes pendientes por caída o capacidad sin volver a sortear el botín."""

import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_death_service import NPCDeathService


class NPCRewardsEffect(TickEffect):
    """Escanea por lotes una sola vez cada cinco segundos, independientemente del usuario."""

    def __init__(self, service: NPCDeathService) -> None:
        """No crea tareas ni timers que sobrevivan al tick del servidor."""
        self.service = service
        self._next = 0.0

    async def apply(
        self,
        user_id: int,  # ruff: ignore[unused-method-argument] - mantenimiento global, firma TickEffect.
        player_repo: PlayerRepository,  # ruff: ignore[unused-method-argument]
        message_sender: MessageSender | None,  # ruff: ignore[unused-method-argument]
    ) -> None:
        """Reclama el intervalo antes de esperar Redis para evitar llamadas simultáneas."""
        now = time.monotonic()
        if now >= self._next:
            self._next = now + self.get_interval_seconds()
            await self.service.recover_pending()

    def get_interval_seconds(self) -> float:
        """Devuelve el plazo de mantenimiento.

        Returns:
            Cinco segundos entre lotes.
        """
        return 5.0

    def get_name(self) -> str:
        """Identifica las métricas del mantenimiento.

        Returns:
            Nombre estable del efecto.
        """
        return "NPCRewards"
