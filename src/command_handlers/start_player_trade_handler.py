"""Handler para iniciar comercio entre jugadores."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.start_player_trade_command import StartPlayerTradeCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class StartPlayerTradeCommandHandler(CommandHandler):
    """Orquesta el inicio de un comercio entre jugadores."""

    def __init__(
        self,
        trade_service: TradeService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de comercio.

        Args:
            trade_service: Servicio que gestiona las sesiones de intercambio.
            message_sender: Enviador de mensajes hacia el cliente.
        """
        self.trade_service = trade_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Procesa el comando de inicio de comercio.

        Returns:
            CommandResult con el estado de la operación.
        """
        if not isinstance(command, StartPlayerTradeCommand):
            return CommandResult.error("Comando inválido")

        if not self.trade_service:
            await self.message_sender.send_console_msg(
                "El sistema de comercio entre jugadores no está disponible todavía.",
                font_color=1,
            )
            return CommandResult.error("TradeService no disponible")

        try:
            success, message = await self.trade_service.request_trade(
                initiator_id=command.initiator_id,
                target_username=command.target_username,
            )
        except Exception:
            logger.exception("Error al iniciar comercio entre jugadores")
            await self.message_sender.send_console_msg(
                "Error interno al iniciar comercio.",
                font_color=1,
            )
            return CommandResult.error("Error interno")

        await self.message_sender.send_console_msg(
            message,
            font_color=7 if success else 1,
        )
        return CommandResult.ok(data={"success": success, "message": message})
