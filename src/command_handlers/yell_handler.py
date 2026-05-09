"""Handler para comando de grito (YELL)."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.yell_command import YellCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

YELL_RANGE_TILES = 20


class YellCommandHandler(CommandHandler):
    """Handler para comando de grito (solo lógica de negocio).

    YELL envía el mensaje a todos los jugadores en el mapa,
    igual que TALK pero con un indicador visual diferente en el cliente.
    """

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa el handler.

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

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de grito.

        Args:
            command: Comando a procesar.

        Returns:
            Resultado del comando.
        """
        if not isinstance(command, YellCommand):
            return CommandResult.error("Comando inválido: se esperaba YellCommand")

        user_id = command.user_id
        message = command.message

        if not self.map_manager:
            return CommandResult.error("MapManager no disponible")

        username = "Desconocido"
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        position = await self.player_repo.get_position(user_id)
        if not position:
            return CommandResult.error("No se encontró posición del jugador")

        map_id = position["map"]

        formatted_message = f"¡{username} grita!: {message}"

        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)
        for sender in all_senders:
            await sender.send_console_msg(formatted_message, font_color=4)

        logger.info(
            "YELL de user_id %d: '%s' enviado a %d jugadores en mapa %d",
            user_id,
            message,
            len(all_senders),
            map_id,
        )

        return CommandResult.ok(data={"user_id": user_id, "message": message, "map_id": map_id})
