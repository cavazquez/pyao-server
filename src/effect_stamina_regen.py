"""Efecto de regeneración de stamina/energía."""

import logging
from typing import TYPE_CHECKING

from src.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.stamina_service import StaminaService

logger = logging.getLogger(__name__)

# Constantes de regeneración
STAMINA_REGEN_RATE = 2  # Puntos regenerados por tick (cada 1 segundo)


class StaminaRegenEffect(TickEffect):
    """Efecto de regeneración de stamina.

    La stamina se regenera automáticamente cada tick si:
    - El jugador tiene hambre > 0
    - El jugador tiene sed > 0

    Si alguno de estos valores es 0, la stamina no se regenera.
    """

    def __init__(self, stamina_service: StaminaService, interval_seconds: float = 1.0) -> None:
        """Inicializa el efecto de regeneración de stamina.

        Args:
            stamina_service: Servicio de stamina.
            interval_seconds: Intervalo en segundos entre regeneraciones.
        """
        self.stamina_service = stamina_service
        self.interval_seconds = interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "StaminaRegen"

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre ejecuciones.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    async def apply(
        self,
        user_id: int,
        _player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica la regeneración de stamina.

        Args:
            user_id: ID del jugador.
            _player_repo: Repositorio de jugadores (no usado, requerido por interfaz).
            message_sender: MessageSender para enviar updates.
        """
        # Verificar si el jugador debería regenerar stamina
        should_regen = await self.stamina_service.should_regenerate(user_id)
        if not should_regen:
            logger.debug(
                "Jugador %d no regenera stamina (hambre o sed en 0)",
                user_id,
            )
            return

        # Regenerar stamina
        await self.stamina_service.regenerate_stamina(
            user_id=user_id,
            amount=STAMINA_REGEN_RATE,
            message_sender=message_sender,
        )
