"""Tarea para desconexión de usuarios."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskQuit(Task):
    """Tarea que maneja la desconexión ordenada del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Quit.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la desconexión ordenada del jugador."""
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.info(
                "Solicitud de desconexión sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        # Convertir user_id a int
        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        # Obtener username
        username = "Desconocido"
        if self.session_data and "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        logger.info(
            "Jugador %d (%s) solicitó desconexión desde %s",
            user_id_int,
            username,
            self.message_sender.connection.address,
        )

        # Obtener posición del jugador antes de removerlo
        if self.player_repo and self.map_manager:
            position = await self.player_repo.get_position(user_id_int)
            if position:
                map_id = position["map"]

                # Notificar a otros jugadores en el mapa que el personaje se fue
                other_senders = self.map_manager.get_all_message_senders_in_map(
                    map_id, exclude_user_id=user_id_int
                )
                for sender in other_senders:
                    await sender.send_character_remove(user_id_int)

                logger.debug(
                    "CHARACTER_REMOVE enviado a %d jugadores en mapa %d",
                    len(other_senders),
                    map_id,
                )

        # Remover jugador del MapManager
        if self.map_manager:
            self.map_manager.remove_player_from_all_maps(user_id_int)
            logger.debug("Jugador %d removido del MapManager", user_id_int)

        # Limpiar sesión
        if self.session_data:
            self.session_data.clear()
            logger.debug("Sesión limpiada para user_id %d", user_id_int)

        # Cerrar la conexión
        self.message_sender.connection.close()
        await self.message_sender.connection.wait_closed()
        logger.info("Jugador %d (%s) desconectado correctamente", user_id_int, username)
