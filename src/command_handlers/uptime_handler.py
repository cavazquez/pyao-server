"""Handler para comando de uptime del servidor."""

import logging
import time
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.uptime_command import UptimeCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class UptimeCommandHandler(CommandHandler):
    """Handler para comando de uptime del servidor (solo lógica de negocio)."""

    def __init__(
        self,
        server_repo: ServerRepository | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            server_repo: Repositorio del servidor.
            message_sender: Enviador de mensajes.
        """
        self.server_repo = server_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de uptime del servidor (solo lógica de negocio).

        Args:
            command: Comando de uptime.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, UptimeCommand):
            return CommandResult.error("Comando inválido: se esperaba UptimeCommand")

        logger.debug(
            "UptimeCommandHandler: solicitud de uptime desde %s",
            self.message_sender.connection.address,
        )

        try:
            # Obtener timestamp de inicio desde el repositorio
            if self.server_repo:
                start_time = await self.server_repo.get_uptime_start()
                if start_time:
                    # Calcular uptime
                    current_time = int(time.time())
                    uptime_seconds = current_time - start_time

                    # Convertir a formato legible
                    days = uptime_seconds // 86400
                    hours = (uptime_seconds % 86400) // 3600
                    minutes = (uptime_seconds % 3600) // 60
                    seconds = uptime_seconds % 60

                    # Formatear mensaje
                    uptime_parts = []
                    if days > 0:
                        uptime_parts.append(f"{days} dia{'s' if days != 1 else ''}")
                    if hours > 0:
                        uptime_parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
                    if minutes > 0:
                        uptime_parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
                    if seconds > 0 or not uptime_parts:
                        uptime_parts.append(f"{seconds} segundo{'s' if seconds != 1 else ''}")

                    uptime_str = ", ".join(uptime_parts)
                    message = f"El servidor lleva activo: {uptime_str}"
                else:
                    message = "No se pudo obtener el tiempo de actividad del servidor"
            else:
                message = "Informacion de uptime no disponible"

            # Enviar mensaje
            await self.message_sender.send_console_msg(message)
            logger.debug("Uptime enviado a %s", self.message_sender.connection.address)

            return CommandResult.ok(data={"message": message})

        except Exception:
            logger.exception("Error al procesar solicitud de uptime")
            return CommandResult.error("Error interno al procesar uptime")
