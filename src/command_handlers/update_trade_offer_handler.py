"""Handler para modificar ofertas de comercio entre jugadores."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.update_trade_offer_command import UpdateTradeOfferCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class UpdateTradeOfferCommandHandler(CommandHandler):
    """Actualiza la oferta de items/oro en la sesión de comercio."""

    def __init__(self, trade_service: TradeService | None, message_sender: MessageSender) -> None:
        """Inicializa el handler para ofertas."""
        self.trade_service = trade_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Procesa el cambio de oferta.

        Returns:
            CommandResult con el resultado de la operación.
        """
        if not isinstance(command, UpdateTradeOfferCommand):
            return CommandResult.error("Comando inválido para UpdateTradeOfferCommandHandler")

        if not self.trade_service:
            await self.message_sender.send_console_msg(
                "El sistema de comercio entre jugadores no está disponible.",
                font_color=1,
            )
            return CommandResult.error("TradeService no disponible")

        try:
            success, message = await self.trade_service.update_offer(
                user_id=command.user_id,
                slot=command.slot,
                quantity=command.quantity,
            )
        except Exception:
            logger.exception("Error actualizando oferta de comercio")
            await self.message_sender.send_console_msg(
                "Error interno al actualizar la oferta.",
                font_color=1,
            )
            return CommandResult.error("Error interno")

        await self.message_sender.send_console_msg(
            message,
            font_color=7 if success else 1,
        )

        if success:
            return CommandResult.ok(data={"success": True, "message": message})
        return CommandResult.error(message)
