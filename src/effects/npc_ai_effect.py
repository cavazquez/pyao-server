"""Efecto de IA para NPCs hostiles en el GameTick."""

import logging
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_ai_service import NPCAIService
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)


class NPCAIEffect(TickEffect):
    """Efecto que procesa la IA de NPCs hostiles cada tick."""

    def __init__(
        self,
        npc_service: NPCService,
        npc_ai_service: NPCAIService,
        interval_seconds: float = 2.0,
    ) -> None:
        """Inicializa el efecto de IA.

        Args:
            npc_service: Servicio de NPCs.
            npc_ai_service: Servicio de IA de NPCs.
            interval_seconds: Intervalo entre ejecuciones en segundos.
        """
        self.npc_service = npc_service
        self.npc_ai_service = npc_ai_service
        self.interval_seconds = interval_seconds

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto para logging.

        Returns:
            Nombre del efecto.
        """
        return "NPCAI"

    async def apply(
        self,
        user_id: int,  # noqa: ARG002
        player_repo: PlayerRepository,  # noqa: ARG002
        message_sender: MessageSender | None,  # noqa: ARG002
    ) -> None:
        """Ejecuta la IA para todos los NPCs hostiles.

        Args:
            user_id: ID del usuario (no usado en este efecto).
            player_repo: Repositorio de jugadores (no usado en este efecto).
            message_sender: MessageSender (no usado en este efecto).
        """
        # Obtener todos los NPCs del mundo
        all_npcs = self.npc_service.map_manager.get_all_npcs()

        hostile_count = 0
        for npc in all_npcs:
            if npc.is_hostile and npc.hp > 0:
                hostile_count += 1
                await self.npc_ai_service.process_hostile_npc(npc)

        if hostile_count > 0:
            logger.debug("Procesados %d NPCs hostiles", hostile_count)
