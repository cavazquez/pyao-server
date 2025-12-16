"""Handler especializado para mensajes de chat público."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TalkPublicHandler:
    """Handler especializado para mensajes de chat público."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa el handler de chat público.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para broadcast.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender
        self.session_data = session_data if session_data is not None else {}

    async def handle_public_message(
        self, user_id: int, message: str
    ) -> tuple[bool, str | None, dict[str, int | str] | None]:
        """Maneja un mensaje de chat público.

        Args:
            user_id: ID del usuario que envía el mensaje.
            message: Contenido del mensaje.

        Returns:
            Tupla (success, error_message, data).
        """
        if not self.map_manager:
            return False, "MapManager no disponible", None

        # Obtener el nombre del usuario
        username = "Desconocido"
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        # Obtener el mapa del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return False, "No se encontró posición del jugador", None

        map_id = position["map"]

        # Formatear mensaje con el nombre del usuario
        formatted_message = f"{username}: {message}"

        # Enviar a todos los jugadores en el mapa (incluyendo el emisor)
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)
        for sender in all_senders:
            await sender.send_console_msg(formatted_message)

        logger.debug(
            "Mensaje de chat de user %d enviado a %d jugadores en mapa %d",
            user_id,
            len(all_senders),
            map_id,
        )

        return (
            True,
            None,
            {
                "user_id": user_id,
                "username": username,
                "message": message,
                "map_id": map_id,
                "recipients": len(all_senders),
            },
        )
