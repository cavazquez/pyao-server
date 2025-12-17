"""Handler especializado para ejecución de lanzar hechizo."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.player.spell_service import SpellService

logger = logging.getLogger(__name__)


class CastSpellExecutionHandler:
    """Handler especializado para ejecución de lanzar hechizo."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        spell_service: SpellService,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de ejecución.

        Args:
            player_repo: Repositorio de jugadores.
            spell_service: Servicio de hechizos.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.spell_service = spell_service
        self.message_sender = message_sender

    async def calculate_target(
        self, user_id: int, target_x: int | None, target_y: int | None
    ) -> tuple[int, int] | None:
        """Calcula las coordenadas del target.

        Si no se proporcionan coordenadas, las calcula según el heading del jugador.

        Args:
            user_id: ID del usuario.
            target_x: Coordenada X del target (opcional).
            target_y: Coordenada Y del target (opcional).

        Returns:
            Tupla (target_x, target_y) o None si no se puede obtener la posición.
        """
        # Si ya hay coordenadas, usarlas
        if target_x is not None and target_y is not None:
            return (target_x, target_y)

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se encontró posición para user_id %d", user_id)
            return None

        player_x = position["x"]
        player_y = position["y"]
        heading = position["heading"]

        # Calcular posición del target según heading
        target_x = player_x
        target_y = player_y

        if heading == 1:  # Norte
            target_y -= 1
        elif heading == 2:  # Este  # noqa: PLR2004
            target_x += 1
        elif heading == 3:  # Sur  # noqa: PLR2004
            target_y += 1
        elif heading == 4:  # Oeste  # noqa: PLR2004
            target_x -= 1

        logger.debug("Target calculado según heading %d: (%d, %d)", heading, target_x, target_y)

        return (target_x, target_y)

    async def execute_spell(
        self, user_id: int, spell_id: int, target_x: int, target_y: int
    ) -> tuple[bool, str | None]:
        """Ejecuta el hechizo.

        Args:
            user_id: ID del usuario.
            spell_id: ID del hechizo.
            target_x: Coordenada X del target.
            target_y: Coordenada Y del target.

        Returns:
            Tupla (success, error_message).
        """
        success = await self.spell_service.cast_spell(
            user_id, spell_id, target_x, target_y, self.message_sender
        )

        if not success:
            logger.debug("Fallo al lanzar hechizo")
            return False, "Fallo al lanzar el hechizo."
        return True, None
