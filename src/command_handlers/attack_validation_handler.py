"""Handler especializado para validaciones de ataque."""

import logging
from typing import TYPE_CHECKING

from src.services.player.stamina_service import STAMINA_COST_ATTACK
from src.utils.sounds import SoundID

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.player.stamina_service import StaminaService
else:
    NPC = object  # Para type hints en runtime

logger = logging.getLogger(__name__)


class AttackValidationHandler:
    """Handler especializado para validaciones de ataque."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        stamina_service: StaminaService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de validaciones.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            stamina_service: Servicio de stamina.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.stamina_service = stamina_service
        self.message_sender = message_sender

    async def validate_attack(
        self, user_id: int, target_x: int, target_y: int, map_id: int
    ) -> tuple[bool, str | None, dict[str, int] | None, NPC | None]:
        """Valida si el jugador puede atacar y encuentra el NPC objetivo.

        Args:
            user_id: ID del usuario.
            target_x: Coordenada X del objetivo.
            target_y: Coordenada Y del objetivo.
            map_id: ID del mapa.

        Returns:
            Tupla (can_attack, error_message, position, target_npc).
        """
        # Consumir stamina por ataque
        if self.stamina_service:
            can_attack = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_ATTACK,
                message_sender=self.message_sender,
            )

            if not can_attack:
                logger.debug("user_id %d no tiene suficiente stamina para atacar", user_id)
                return False, "No tienes suficiente stamina para atacar.", None, None

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.error("No se encontró posición para user_id %d", user_id)
            return False, "No se encontró posición del jugador.", None, None

        player_x = position["x"]
        player_y = position["y"]

        logger.debug(
            "Jugador %d ataca desde (%d,%d) hacia (%d,%d) en mapa %d",
            user_id,
            player_x,
            player_y,
            target_x,
            target_y,
            map_id,
        )

        # Buscar NPC en la posición objetivo
        target_npc = None
        all_npcs = self.map_manager.get_all_npcs()

        for npc in all_npcs:
            if npc.map_id == map_id and npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        if not target_npc:
            # No hay NPC en esa posición
            logger.debug("No hay NPC en posición (%d,%d)", target_x, target_y)
            await self.message_sender.send_console_msg("No hay nada que atacar ahí.")
            # Reproducir sonido de miss
            await self.message_sender.send_play_wave(SoundID.MISS, player_x, player_y)
            return False, "No hay nada que atacar ahí.", position, None

        # Verificar que el NPC sea atacable
        if not target_npc.is_attackable:
            await self.message_sender.send_console_msg(f"No puedes atacar a {target_npc.name}.")
            return False, f"No puedes atacar a {target_npc.name}.", position, None

        return True, None, position, target_npc
