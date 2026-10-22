"""Handler para comando de ayuda."""

import logging
from typing import TYPE_CHECKING

from src.commands.ayuda_command import AyudaCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.services.classic_chat.catalog import help_text

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class AyudaCommandHandler(CommandHandler):
    """Handler para comando de ayuda (solo lógica de negocio)."""

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
        """Ejecuta el comando de ayuda (solo lógica de negocio).

        Args:
            command: Comando de ayuda.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, AyudaCommand):
            return CommandResult.error("Comando inválido: se esperaba AyudaCommand")

        logger.debug(
            "AyudaCommandHandler: solicitud de ayuda desde %s",
            self.message_sender.address,
        )

        try:
            help_message = help_text()

            # Enviar ayuda línea por línea
            await self.message_sender.send_multiline_console_msg(help_message)
            logger.debug("Ayuda enviada a %s", self.message_sender.address)

            return CommandResult.ok(data={"help_message": help_message})

        except Exception:
            logger.exception("Error al procesar solicitud de ayuda")
            return CommandResult.error("Error interno al procesar ayuda")
