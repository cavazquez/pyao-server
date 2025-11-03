"""Tarea para manejar comandos de Game Master (GM)."""

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.player_map_service import PlayerMapService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class TaskGMCommands(Task):
    """Tarea que maneja comandos de Game Master."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        player_map_service: PlayerMapService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de comandos GM.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast multijugador.
            player_map_service: Servicio de mapas de jugador.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.player_map_service = player_map_service
        self.session_data = session_data

    def _parse_packet(self) -> tuple[int, str, int, int, int] | None:
        """Parsea y valida el paquete de comando GM (teletransporte).

        El formato esperado es:
        - Byte 0: PacketID (GM_COMMANDS = 122)
        - Byte 1: Subcomando GM (ej: WARP_CHAR)
        - String: Username (UTF-16LE con length prefix)
        - Int16: Map ID
        - Byte: X
        - Byte: Y

        Returns:
            Tupla (subcommand, username, map_id, x, y) o None si hay error.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        result = validator.validate_gm_teleport()

        if validator.has_errors():
            logger.warning("Error validando GM_COMMANDS: %s", validator.get_error_message())
            return None

        return result

    async def execute(self) -> None:
        """Ejecuta el comando GM de teletransporte."""
        # Parsear parámetros
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete GM_COMMANDS inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        subcommand, username, map_id, x, y = parsed

        logger.info(
            "Comando GM recibido: subcommand=%d, username=%s, map=%d, pos=(%d,%d)",
            subcommand,
            username,
            map_id,
            x,
            y,
        )

        # Verificar que el player_repo esté disponible
        if self.player_repo is None:
            logger.error("PlayerRepository no está disponible para comando GM")
            return

        # Obtener user_id de la sesión
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de comando GM sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Debug: mostrar bytes del username
        logger.debug(
            "Username recibido: '%s' (bytes: %s)",
            username,
            username.encode("utf-8").hex() if username else "empty",
        )

        # Si el username es "YO" o está vacío, teletransportar al propio jugador
        # El cliente Godot envía "YO" pero puede llegar con encoding diferente
        if not username or username.upper() == "YO" or username == "余":
            await self._teleport_player(user_id, map_id, x, y)
        else:
            # TODO: Implementar teletransporte de otros jugadores (requiere buscar por username)
            await self.message_sender.send_console_msg(
                "Teletransporte de otros jugadores no implementado aún."
            )
            logger.info("Teletransporte de otros jugadores no implementado: %s", username)

    async def _teleport_player(self, user_id: int, new_map: int, new_x: int, new_y: int) -> None:
        """Teletransporta un jugador a una nueva posición.

        Args:
            user_id: ID del jugador.
            new_map: ID del nuevo mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
        """
        if not self.player_repo or not self.player_map_service:
            logger.error("Dependencias no disponibles para teletransporte")
            return

        # Obtener posición actual
        position = await self.player_repo.get_position(user_id)
        if position is None:
            logger.warning("No se encontró posición para user_id %d", user_id)
            return

        current_map = position["map"]
        current_x = position["x"]
        current_y = position["y"]
        current_heading = position.get("heading", 3)

        # Si es el mismo mapa, usar teleport_in_same_map
        if current_map == new_map:
            await self.player_map_service.teleport_in_same_map(
                user_id=user_id,
                map_id=current_map,
                old_x=current_x,
                old_y=current_y,
                new_x=new_x,
                new_y=new_y,
                heading=current_heading,
                message_sender=self.message_sender,
            )
        # Cambio de mapa - usar transition_to_map
        else:
            await self.player_map_service.transition_to_map(
                user_id=user_id,
                current_map=current_map,
                current_x=current_x,
                current_y=current_y,
                new_map=new_map,
                new_x=new_x,
                new_y=new_y,
                heading=current_heading,
                message_sender=self.message_sender,
            )
