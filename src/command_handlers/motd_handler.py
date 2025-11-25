"""Handler para comando de mensaje del día."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.motd_command import MotdCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class MotdCommandHandler(CommandHandler):
    """Handler para comando de mensaje del día (solo lógica de negocio)."""

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
        """Ejecuta el comando de mensaje del día (solo lógica de negocio).

        Args:
            command: Comando de mensaje del día.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, MotdCommand):
            return CommandResult.error("Comando inválido: se esperaba MotdCommand")

        logger.debug(
            "MotdCommandHandler: solicitud de MOTD desde %s",
            self.message_sender.connection.address,
        )

        try:
            # Obtener MOTD desde el repositorio
            if self.server_repo:
                motd = await self.server_repo.get_motd()
            else:
                # Mensaje por defecto si no hay repositorio
                motd = "» Bienvenido a Argentum Online! «\n• Servidor en desarrollo."

            # Enviar MOTD línea por línea
            await self.message_sender.send_multiline_console_msg(motd)
            logger.info("MOTD enviado a %s", self.message_sender.connection.address)

            return CommandResult.ok(data={"motd": motd})

        except Exception:
            logger.exception("Error al procesar solicitud de MOTD")
            return CommandResult.error("Error interno al procesar MOTD")
