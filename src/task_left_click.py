"""Tarea para click izquierdo en personajes/NPCs."""

import logging
import struct
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.npc import NPC
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskLeftClick(Task):
    """Maneja click izquierdo en personajes/NPCs."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de click izquierdo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta click izquierdo en personaje/NPC."""
        # Parsear el packet: PacketID (1 byte) + X (1 byte) + Y (1 byte)
        min_packet_size = 3
        if len(self.data) < min_packet_size:
            logger.warning("Packet LEFT_CLICK inválido: tamaño incorrecto")
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de click sin estar logueado")
            return

        if not self.map_manager or not self.player_repo:
            logger.error("Dependencias no disponibles para click en NPC")
            return

        try:
            # Extraer coordenadas X, Y (1 byte cada una)
            x = struct.unpack("B", self.data[1:2])[0]
            y = struct.unpack("B", self.data[2:3])[0]

            logger.info("user_id %d hizo click en posición (%d, %d)", user_id, x, y)

            # Obtener posición del jugador para saber en qué mapa está
            position = await self.player_repo.get_position(user_id)
            if not position:
                logger.warning("No se pudo obtener posición del jugador %d", user_id)
                return

            map_id = position["map"]

            # Buscar NPC en esa posición
            all_npcs = self.map_manager.get_npcs_in_map(map_id)
            npc_found = None
            for npc in all_npcs:
                if npc.x == x and npc.y == y:
                    npc_found = npc
                    break

            if npc_found:
                await self._handle_npc_click(user_id, npc_found)
            else:
                # No hay NPC en esa posición, podría ser otro jugador
                logger.debug("No se encontró NPC en posición (%d, %d) del mapa %d", x, y, map_id)
                await self.message_sender.send_console_msg(f"No hay nadie en ({x}, {y}).")

        except struct.error:
            logger.exception("Error al parsear packet LEFT_CLICK")

    async def _handle_npc_click(self, user_id: int, npc: NPC) -> None:
        """Maneja click en un NPC.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC.
        """
        # Mostrar información básica del NPC (solo ASCII para evitar crashes)
        info_parts = [f"[{npc.name}]"]

        if npc.description:
            info_parts.append(npc.description)

        if npc.is_hostile:
            info_parts.append(f"Nivel {npc.level} - Hostil")
        else:
            info_parts.append(f"Nivel {npc.level} - Amigable")

        info_parts.append(f"HP: {npc.hp}/{npc.max_hp}")

        info_message = " | ".join(info_parts)
        await self.message_sender.send_console_msg(info_message)

        logger.info(
            "user_id %d obtuvo información de NPC %s (CharIndex: %d)",
            user_id,
            npc.name,
            npc.char_index,
        )
