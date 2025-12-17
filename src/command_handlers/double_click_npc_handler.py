"""Handler especializado para doble click en NPCs."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class DoubleClickNPCHandler:
    """Handler especializado para doble click en NPCs."""

    def __init__(
        self,
        map_manager: MapManager | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de NPCs.

        Args:
            map_manager: Gestor de mapas para obtener NPCs.
            message_sender: Enviador de mensajes.
        """
        self.map_manager = map_manager
        self.message_sender = message_sender

    async def handle_npc_double_click(
        self, user_id: int, char_index: int, map_id: int | None
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Maneja doble click en un NPC.

        Args:
            user_id: ID del usuario.
            char_index: CharIndex del NPC.
            map_id: ID del mapa donde está el jugador.

        Returns:
            Tupla (success, error_message, result_data).
        """
        if not self.map_manager:
            logger.error("MapManager no disponible para interacción con NPC")
            return False, "Error interno: gestor de mapas no disponible", None

        if not map_id:
            logger.error("map_id no disponible para interacción con NPC")
            return False, "Error interno: mapa no disponible", None

        # Buscar el NPC en el mapa
        npc = self.map_manager.get_npc_by_char_index(map_id, char_index)
        if not npc:
            logger.warning(
                "user_id %d intentó interactuar con NPC inexistente (CharIndex: %d)",
                user_id,
                char_index,
            )
            await self.message_sender.send_console_msg("No hay nadie ahí.")
            return False, "No hay nadie ahí", None

        # Interactuar según el tipo de NPC
        if npc.is_hostile:
            # NPC hostil - preparar para combate
            await self.message_sender.send_console_msg(
                f"{npc.name} te mira con hostilidad. Sistema de combate en desarrollo."
            )
        else:
            # NPC amigable - mostrar diálogo
            await self.message_sender.send_console_msg(
                f"{npc.name}: {npc.description or 'Hola, aventurero.'}"
            )

        logger.info(
            "user_id %d interactuó con NPC %s (CharIndex: %d)",
            user_id,
            npc.name,
            char_index,
        )

        return (
            True,
            None,
            {
                "npc_name": npc.name,
                "char_index": char_index,
                "is_hostile": npc.is_hostile,
            },
        )
