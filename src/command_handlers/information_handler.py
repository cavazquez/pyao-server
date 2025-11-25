"""Handler para comando de información del servidor."""

import logging
import time
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.information_command import InformationCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class InformationCommandHandler(CommandHandler):
    """Handler para comando de información del servidor (solo lógica de negocio)."""

    def __init__(
        self,
        server_repo: ServerRepository | None,
        map_manager: MapManager | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            server_repo: Repositorio del servidor.
            map_manager: Gestor de mapas para contar jugadores.
            message_sender: Enviador de mensajes.
        """
        self.server_repo = server_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de información del servidor (solo lógica de negocio).

        Args:
            command: Comando de información del servidor.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, InformationCommand):
            return CommandResult.error("Comando inválido: se esperaba InformationCommand")

        logger.debug(
            "InformationCommandHandler: solicitud de información desde %s",
            self.message_sender.connection.address,
        )

        try:
            # Construir mensaje de información
            info_parts = ["--- Informacion del Servidor ---"]

            # Nombre del servidor
            info_parts.extend(["Nombre: Argentum Online", "Version: PyAO 0.1.0"])

            # Jugadores online
            if self.map_manager:
                players = self.map_manager.get_all_connected_players()
                player_count = len(players)
                info_parts.append(f"Jugadores conectados: {player_count}")
            else:
                info_parts.append("Jugadores conectados: N/A")

            # Uptime
            if self.server_repo:
                start_time = await self.server_repo.get_uptime_start()
                if start_time:
                    current_time = int(time.time())
                    uptime_seconds = current_time - start_time

                    # Formato resumido
                    days = uptime_seconds // 86400
                    hours = (uptime_seconds % 86400) // 3600
                    minutes = (uptime_seconds % 3600) // 60

                    if days > 0:
                        uptime_str = f"{days}d {hours}h {minutes}m"
                    elif hours > 0:
                        uptime_str = f"{hours}h {minutes}m"
                    else:
                        uptime_str = f"{minutes}m"

                    info_parts.append(f"Uptime: {uptime_str}")

            # Comandos disponibles
            info_parts.append("Usa /AYUDA para ver comandos")

            # Unir todo con saltos de línea
            message = "\n".join(info_parts)

            # Enviar información línea por línea
            await self.message_sender.send_multiline_console_msg(message)
            logger.debug("Información enviada a %s", self.message_sender.connection.address)

            return CommandResult.ok(data={"message": message})

        except Exception:
            logger.exception("Error al procesar solicitud de información")
            return CommandResult.error("Error interno al procesar información")
