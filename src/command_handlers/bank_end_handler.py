"""Handler para comando de cerrar ventana del banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_end_command import BankEndCommand
from src.commands.base import Command, CommandHandler, CommandResult

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class BankEndCommandHandler(CommandHandler):
    """Handler para comando de cerrar ventana del banco (solo lógica de negocio)."""

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
        """Ejecuta el comando de cerrar ventana del banco (solo lógica de negocio).

        Args:
            command: Comando de cerrar ventana del banco.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, BankEndCommand):
            return CommandResult.error("Comando inválido: se esperaba BankEndCommand")

        user_id = command.user_id

        if user_id is None:
            # Es normal recibir este paquete antes del login
            logger.debug("BankEndCommandHandler: BANK_END recibido sin sesión (pre-login)")
            return CommandResult.ok(data={"pre_login": True})

        logger.info("BankEndCommandHandler: user_id %d cerró la ventana del banco", user_id)

        try:
            # Enviar confirmación al cliente para cerrar la ventana
            await self.message_sender.send_bank_end()
            logger.debug("BANK_END enviado a user_id %d", user_id)

            return CommandResult.ok(data={"user_id": user_id})

        except Exception:
            logger.exception("Error al procesar cierre de ventana del banco")
            return CommandResult.error("Error interno al procesar cierre de banco")
