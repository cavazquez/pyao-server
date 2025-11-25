"""Handler para comando de ping."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.ping_command import PingCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class PingCommandHandler(CommandHandler):
    """Handler para comando de ping (solo lógica de negocio)."""

    def __init__(
        self,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            message_sender: Enviador de mensajes.
        """
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de ping (solo lógica de negocio).

        Args:
            command: Comando de ping.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, PingCommand):
            return CommandResult.error("Comando inválido: se esperaba PingCommand")

        logger.debug(
            "PingCommandHandler: ping recibido desde %s",
            self.message_sender.connection.address,
        )

        try:
            # Enviar paquete PONG usando MessageSender
            await self.message_sender.send_pong()
            logger.debug("Pong enviado a %s", self.message_sender.connection.address)

            return CommandResult.ok()

        except Exception:
            logger.exception("Error al procesar ping")
            return CommandResult.error("Error interno al procesar ping")
