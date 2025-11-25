"""Handler para comando de lista de jugadores online."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.online_command import OnlineCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class OnlineCommandHandler(CommandHandler):
    """Handler para comando de lista de jugadores online (solo lógica de negocio)."""

    def __init__(
        self,
        map_manager: MapManager,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            map_manager: Gestor de mapas.
            message_sender: Enviador de mensajes.
        """
        self.map_manager = map_manager
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de lista de jugadores online (solo lógica de negocio).

        Args:
            command: Comando de lista de jugadores online.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, OnlineCommand):
            return CommandResult.error("Comando inválido: se esperaba OnlineCommand")

        user_id = command.user_id

        logger.info("OnlineCommandHandler: solicitud de jugadores online de user_id %d", user_id)

        try:
            # Obtener todos los jugadores conectados
            all_players = self.map_manager.get_all_connected_players()

            if not all_players:
                await self.message_sender.send_console_msg("No hay jugadores conectados")
                return CommandResult.ok(data={"user_id": user_id, "players": [], "count": 0})

            # Formatear mensaje con la lista de jugadores
            online_message = f"--- Jugadores Online ({len(all_players)}) ---\n"
            for username in sorted(all_players):
                online_message += f"{username}\n"

            # Enviar lista línea por línea
            await self.message_sender.send_multiline_console_msg(online_message.rstrip())
            logger.info("Lista de jugadores online enviada a user_id %d", user_id)

            return CommandResult.ok(
                data={"user_id": user_id, "players": sorted(all_players), "count": len(all_players)}
            )

        except Exception:
            logger.exception("Error al procesar solicitud de jugadores online")
            return CommandResult.error("Error interno al procesar jugadores online")
