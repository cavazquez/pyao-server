"""Handler especializado para validaciones de lanzar hechizo."""

import logging
from typing import TYPE_CHECKING

from src.services.player.stamina_service import STAMINA_COST_SPELL

# Constantes para validación de coordenadas
MAX_COORD = 100
MAX_SPELL_RANGE = 10

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.spellbook_repository import SpellbookRepository
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)


class CastSpellValidationHandler:
    """Handler especializado para validaciones de lanzar hechizo."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        spellbook_repo: SpellbookRepository,
        stamina_service: StaminaService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de validaciones.

        Args:
            player_repo: Repositorio de jugadores.
            spellbook_repo: Repositorio de libro de hechizos.
            stamina_service: Servicio de stamina.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.spellbook_repo = spellbook_repo
        self.stamina_service = stamina_service
        self.message_sender = message_sender

    async def validate_dependencies(self) -> tuple[bool, str | None]:
        """Valida que las dependencias estén disponibles.

        Returns:
            Tupla (is_valid, error_message).
        """
        if not self.player_repo or not self.spellbook_repo:
            logger.error("Dependencias no disponibles para lanzar hechizo")
            return False, "Error interno: dependencias no disponibles"
        return True, None

    async def validate_stamina(self, user_id: int) -> tuple[bool, str | None]:
        """Valida que el jugador tenga suficiente stamina.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla (is_valid, error_message).
        """
        if self.stamina_service:
            can_cast = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_SPELL,
                message_sender=self.message_sender,
            )

            if not can_cast:
                logger.debug("user_id %d no tiene suficiente stamina para lanzar hechizo", user_id)
                return False, "No tienes suficiente stamina para lanzar el hechizo."
        return True, None

    def validate_coordinates(
        self, target_x: int | None, target_y: int | None
    ) -> tuple[bool, str | None]:
        """Valida las coordenadas del target.

        Args:
            target_x: Coordenada X del target.
            target_y: Coordenada Y del target.

        Returns:
            Tupla (is_valid, error_message).
        """
        if (
            target_x is not None
            and target_y is not None
            and self._are_coordinates_out_of_bounds(target_x, target_y)
        ):
            return False, "Coordenadas inválidas"
        return True, None

    def _are_coordinates_out_of_bounds(self, target_x: int, target_y: int) -> bool:
        """Verifica si las coordenadas están fuera de los límites.

        Args:
            target_x: Coordenada X del target.
            target_y: Coordenada Y del target.

        Returns:
            True si están fuera de límites, False si no.
        """
        return target_x < 1 or target_x > MAX_COORD or target_y < 1 or target_y > MAX_COORD

    async def validate_spell_slot(
        self, user_id: int, slot: int
    ) -> tuple[bool, str | None, int | None]:
        """Valida que el jugador tenga un hechizo en el slot.

        Args:
            user_id: ID del usuario.
            slot: Slot del spellbook.

        Returns:
            Tupla (is_valid, error_message, spell_id).
        """
        spell_id = await self.spellbook_repo.get_spell_in_slot(user_id, slot)
        if spell_id is None:
            logger.warning("user_id %d no tiene hechizo en slot %d (slot vacío)", user_id, slot)
            return False, "No tienes ese hechizo.", None
        return True, None, spell_id

    def validate_range(
        self, player_x: int, player_y: int, target_x: int, target_y: int
    ) -> tuple[bool, str | None]:
        """Valida que el target esté en rango.

        Args:
            player_x: Coordenada X del jugador.
            player_y: Coordenada Y del jugador.
            target_x: Coordenada X del target.
            target_y: Coordenada Y del target.

        Returns:
            Tupla (is_valid, error_message).
        """
        distance = abs(target_x - player_x) + abs(target_y - player_y)  # Manhattan distance

        if distance > MAX_SPELL_RANGE:
            logger.debug(
                "user_id intentó lanzar hechizo fuera de rango: distancia=%d",
                distance,
            )
            return False, "El objetivo está demasiado lejos para lanzar el hechizo."
        return True, None
