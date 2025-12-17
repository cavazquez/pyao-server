"""Handler especializado para validaciones de movimiento."""

import logging
import time
from typing import TYPE_CHECKING

from src.services.player.stamina_service import STAMINA_COST_WALK

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)


class WalkValidationHandler:
    """Handler especializado para validaciones de movimiento."""

    def __init__(
        self,
        player_repo: PlayerRepository | None,
        stamina_service: StaminaService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de validaciones.

        Args:
            player_repo: Repositorio de jugadores.
            stamina_service: Servicio de stamina.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.stamina_service = stamina_service
        self.message_sender = message_sender

    async def validate_movement(self, user_id: int) -> tuple[bool, str | None]:
        """Valida si el jugador puede moverse.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla (can_move, error_message). can_move=True si puede moverse.
        """
        if not self.player_repo:
            logger.error("PlayerRepository no está disponible para movimiento")
            return False, "Error interno: repositorio no disponible"

        # Verificar si el jugador está inmovilizado
        immobilized_until = await self.player_repo.get_immobilized_until(user_id)
        if immobilized_until > 0.0:
            current_time = time.time()
            if current_time < immobilized_until:
                await self.message_sender.send_console_msg(
                    "¡Estás inmovilizado! No puedes moverte."
                )
                logger.debug(
                    "Jugador user_id %d intentó moverse pero está inmovilizado hasta %.2f",
                    user_id,
                    immobilized_until,
                )
                return False, "Estás inmovilizado. No puedes moverte."

        # Cancelar meditación y consumir stamina
        await self._cancel_meditation_if_active(user_id)

        if not await self._consume_stamina(user_id):
            return False, "No tienes suficiente stamina para moverte."

        return True, None

    async def _cancel_meditation_if_active(self, user_id: int) -> None:
        """Cancela la meditación si el jugador está meditando.

        Args:
            user_id: ID del jugador.
        """
        if not self.player_repo:
            return

        is_meditating = await self.player_repo.is_meditating(user_id)
        if is_meditating:
            await self.player_repo.set_meditating(user_id, is_meditating=False)
            await self.message_sender.send_meditate_toggle()
            await self.message_sender.send_console_msg("Dejas de meditar al moverte.")
            logger.info("user_id %d dejó de meditar al moverse", user_id)

    async def _consume_stamina(self, user_id: int) -> bool:
        """Consume stamina por el movimiento.

        Args:
            user_id: ID del jugador.

        Returns:
            True si se pudo consumir stamina, False si no tiene suficiente.
        """
        if self.stamina_service:
            can_move = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_WALK,
                message_sender=self.message_sender,
            )

            if not can_move:
                logger.debug("user_id %d no tiene suficiente stamina para moverse", user_id)
                return False

        return True
