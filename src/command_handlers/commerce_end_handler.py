"""Handler para comando de cerrar ventana de comercio."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.commerce_end_command import CommerceEndCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class CommerceEndCommandHandler(CommandHandler):
    """Handler para comando de cerrar ventana de comercio (solo lógica de negocio)."""

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
        """Ejecuta el comando de cerrar ventana de comercio (solo lógica de negocio).

        Args:
            command: Comando de cerrar ventana de comercio.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, CommerceEndCommand):
            return CommandResult.error("Comando inválido: se esperaba CommerceEndCommand")

        logger.debug(
            "CommerceEndCommandHandler: cliente %s solicitó cerrar la ventana de comercio",
            self.message_sender.connection.address,
        )

        try:
            # Enviar confirmación para cerrar la ventana
            await self.message_sender.send_commerce_end()
            logger.debug("COMMERCE_END enviado a %s", self.message_sender.connection.address)

            return CommandResult.ok()

        except Exception:
            logger.exception("Error al procesar cierre de ventana de comercio")
            return CommandResult.error("Error interno al procesar cierre de comercio")
