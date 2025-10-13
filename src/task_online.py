"""Tarea para procesar la solicitud de jugadores online."""

import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskOnline(Task):
    """Tarea que maneja la solicitud de jugadores conectados."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Online.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            map_manager: Gestor de mapas.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.map_manager = map_manager
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la solicitud de jugadores online."""
        # Obtener user_id de la sesión
        user_id = None
        if self.session_data:
            user_id = self.session_data.get("user_id")

        if user_id is None:
            logger.warning(
                "Solicitud de online recibida sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        logger.info("Solicitud de jugadores online de user_id %d", user_id)

        if not self.map_manager:
            await self.message_sender.send_console_msg("Error: Servidor no disponible")
            return

        # Obtener todos los jugadores conectados
        all_players = self.map_manager.get_all_connected_players()

        if not all_players:
            await self.message_sender.send_console_msg("No hay jugadores conectados")
            return

        # Formatear mensaje con la lista de jugadores
        online_message = f"--- Jugadores Online ({len(all_players)}) ---\n"
        for username in sorted(all_players):
            online_message += f"{username}\n"

        # Enviar lista línea por línea
        await self.message_sender.send_multiline_console_msg(online_message.rstrip())
        logger.info("Lista de jugadores online enviada a user_id %d", user_id)
