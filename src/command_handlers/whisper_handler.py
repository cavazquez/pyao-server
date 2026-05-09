"""Handler para comando de susurro (WHISPER)."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.whisper_command import WhisperCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class WhisperCommandHandler(CommandHandler):
    """Handler para comando de susurro (solo lógica de negocio).

    WHISPER envía un mensaje privado a un jugador específico.
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
            map_manager: Gestor de mapas para localizar destinatario.
            message_sender: Enviador de mensajes del emisor.
            session_data: Datos de sesión compartidos.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender
        self.session_data = session_data if session_data is not None else {}

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de susurro.

        Args:
            command: Comando a procesar.

        Returns:
            Resultado del comando.
        """
        if not isinstance(command, WhisperCommand):
            return CommandResult.error("Comando inválido: se esperaba WhisperCommand")

        user_id = command.user_id
        receiver_name = command.receiver
        message = command.message

        sender_username = "Desconocido"
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                sender_username = username_value

        if not self.map_manager:
            await self.message_sender.send_console_msg("Servicio no disponible.")
            return CommandResult.error("MapManager no disponible")

        target_user_id = self.map_manager.find_player_by_username(receiver_name)
        if target_user_id is None:
            await self.message_sender.send_console_msg(
                f"El usuario {receiver_name} no está conectado."
            )
            return CommandResult.error(f"Usuario {receiver_name} no encontrado")

        target_sender = self.map_manager.get_player_message_sender(target_user_id)
        if target_sender is None:
            await self.message_sender.send_console_msg(
                f"No se pudo enviar mensaje a {receiver_name}."
            )
            return CommandResult.error(f"Sender no disponible para {receiver_name}")

        formatted_message = f"{sender_username} susurra: {message}"
        await target_sender.send_console_msg(formatted_message, font_color=3)

        await self.message_sender.send_console_msg(
            f"A {receiver_name}: {message}", font_color=3
        )

        logger.info(
            "WHISPER de user_id %d a '%s': '%s'",
            user_id,
            receiver_name,
            message,
        )

        return CommandResult.ok(
            data={"user_id": user_id, "receiver": receiver_name, "message": message}
        )
