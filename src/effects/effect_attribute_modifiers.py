"""Efecto periódico para limpiar modificadores de atributos expirados."""

import logging
import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class AttributeModifiersEffect(TickEffect):
    """Efecto que verifica y limpia modificadores de atributos expirados."""

    def __init__(self, interval_seconds: float = 10.0) -> None:
        """Inicializa el efecto de limpieza de modificadores.

        Args:
            interval_seconds: Intervalo en segundos entre verificaciones (default: 10s).
        """
        self.interval_seconds = interval_seconds

    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Verifica y limpia modificadores de atributos expirados.

        Args:
            user_id: ID del usuario.
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes (puede ser None).
        """
        current_time = time.time()
        needs_update = False

        # Verificar modificador de fuerza
        strength_until, _strength_modifier = await player_repo.get_strength_modifier(user_id)
        if strength_until > 0.0 and current_time >= strength_until:
            # El modificador expiró, limpiarlo
            await player_repo.set_strength_modifier(user_id, 0.0, 0)
            logger.debug("Modificador de fuerza expirado y limpiado para user_id %d", user_id)
            needs_update = True

        # Verificar modificador de agilidad
        agility_until, _agility_modifier = await player_repo.get_agility_modifier(user_id)
        if agility_until > 0.0 and current_time >= agility_until:
            # El modificador expiró, limpiarlo
            await player_repo.set_agility_modifier(user_id, 0.0, 0)
            logger.debug("Modificador de agilidad expirado y limpiado para user_id %d", user_id)
            needs_update = True

        # Si se limpió algún modificador, actualizar atributos en el cliente
        if needs_update and message_sender:
            attributes = await player_repo.get_attributes(user_id)
            if attributes:
                await message_sender.send_update_strength_and_dexterity(
                    strength=attributes.get("strength", 0),
                    dexterity=attributes.get("agility", 0),
                )
                logger.debug(
                    "Atributos actualizados para user_id %d después de limpiar modificadores",
                    user_id,
                )

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "AttributeModifiers"
