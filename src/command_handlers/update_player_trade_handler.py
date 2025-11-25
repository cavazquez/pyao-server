"""Handler para actualizar el estado de comercio entre jugadores."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.update_player_trade_command import TradeUpdateAction, UpdatePlayerTradeCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class UpdatePlayerTradeCommandHandler(CommandHandler):
    """Orquesta las acciones de una sesión de comercio existente."""

    def __init__(self, trade_service: TradeService | None, message_sender: MessageSender) -> None:
        """Inicializa el handler."""
        self.trade_service = trade_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Procesa la acción solicitada.

        Returns:
            CommandResult con éxito o error según la acción ejecutada.
        """
        if not isinstance(command, UpdatePlayerTradeCommand):
            return CommandResult.error("Comando inválido")

        if not self.trade_service:
            await self.message_sender.send_console_msg(
                "El sistema de comercio entre jugadores no está disponible.",
                font_color=1,
            )
            return CommandResult.error("TradeService no disponible")

        try:
            if command.action == TradeUpdateAction.CANCEL:
                success, message = await self.trade_service.cancel_trade(command.user_id)
            elif command.action == TradeUpdateAction.CONFIRM:
                success, message = await self.trade_service.confirm_trade(command.user_id)
            elif command.action == TradeUpdateAction.READY:
                success, message = await self.trade_service.ready_trade(command.user_id)
            elif command.action == TradeUpdateAction.REJECT:
                success, message = await self.trade_service.reject_trade(command.user_id)
            else:
                success, message = False, "Acción de comercio no soportada."
        except Exception:
            logger.exception("Error al actualizar estado de comercio")
            await self.message_sender.send_console_msg(
                "Error interno al actualizar el comercio.",
                font_color=1,
            )
            return CommandResult.error("Error interno")

        if not success:
            await self.message_sender.send_console_msg(message, font_color=1)
            return CommandResult.error(message)

        await self.message_sender.send_console_msg(message, font_color=7)
        return CommandResult.ok(data={"message": message})
