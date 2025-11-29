"""Efecto periódico para eliminar mascotas invocadas expiradas."""

import logging
import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)


class SummonExpiryEffect(TickEffect):
    """Efecto que verifica y elimina mascotas invocadas expiradas."""

    _last_check_time: float = 0.0  # Timestamp de última verificación (clase)

    def __init__(self, npc_service: NPCService, interval_seconds: float = 5.0) -> None:
        """Inicializa el efecto de expiración de invocaciones.

        Args:
            npc_service: Servicio de NPCs para eliminar mascotas expiradas.
            interval_seconds: Intervalo en segundos entre verificaciones (default: 5s).
        """
        self.npc_service = npc_service
        self.interval_seconds = interval_seconds

    async def apply(
        self,
        _user_id: int,
        _player_repo: PlayerRepository,
        _message_sender: MessageSender | None,
    ) -> None:
        """Verifica y elimina mascotas expiradas.

        Nota: Este efecto se ejecuta una vez por jugador, pero solo procesa
        si han pasado suficientes segundos desde la última verificación global.

        Args:
            _user_id: ID del usuario (no usado, requerido por TickEffect).
            _player_repo: Repositorio de jugadores (no usado, requerido por TickEffect).
            _message_sender: Enviador de mensajes (no usado, requerido por TickEffect).
        """
        current_time = time.time()

        # Solo ejecutar si han pasado suficientes segundos desde la última verificación
        if current_time - SummonExpiryEffect._last_check_time < self.interval_seconds:
            return

        # Actualizar timestamp de última verificación
        SummonExpiryEffect._last_check_time = current_time

        # Obtener todos los NPCs del mundo
        all_npcs = await self.npc_service.npc_repository.get_all_npcs()

        # Filtrar solo NPCs invocados expirados
        expired_pets = [
            npc
            for npc in all_npcs
            if npc.summoned_by_user_id > 0
            and npc.summoned_until > 0.0
            and current_time >= npc.summoned_until
        ]

        # Eliminar mascotas expiradas
        for pet in expired_pets:
            logger.info(
                "Mascota expirada eliminada: %s (npc_id=%d) de user_id %d",
                pet.name,
                pet.npc_id,
                pet.summoned_by_user_id,
            )
            await self.npc_service.remove_npc(pet)

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "SummonExpiry"
