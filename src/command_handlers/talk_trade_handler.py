"""Handler especializado para comandos de comercio entre jugadores."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.start_player_trade_handler import StartPlayerTradeCommandHandler
from src.commands.start_player_trade_command import StartPlayerTradeCommand

if TYPE_CHECKING:
    from src.commands.talk_command import TalkCommand
    from src.messaging.message_sender import MessageSender
    from src.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class TalkTradeHandler:
    """Handler especializado para comandos de comercio entre jugadores."""

    def __init__(
        self,
        trade_service: TradeService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de comercio.

        Args:
            trade_service: Servicio de comercio entre jugadores.
            message_sender: Enviador de mensajes.
        """
        self.trade_service = trade_service
        self.message_sender = message_sender

    async def handle_trade_command(self, user_id: int, command: TalkCommand) -> None:
        """Maneja el comando /COMERCIAR."""
        if not self.trade_service:
            await self.message_sender.send_console_msg(
                "El sistema de comercio entre jugadores no está disponible.",
                font_color=1,
            )
            return

        parsed = command.parse_trade_command()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Uso: /COMERCIAR <usuario>",
                font_color=1,
            )
            return

        _, args = parsed
        if not args:
            await self.message_sender.send_console_msg(
                "Uso: /COMERCIAR <usuario>",
                font_color=1,
            )
            return

        target_username = args[0]
        trade_handler = StartPlayerTradeCommandHandler(
            trade_service=self.trade_service,
            message_sender=self.message_sender,
        )
        trade_command = StartPlayerTradeCommand(
            initiator_id=user_id,
            target_username=target_username,
        )
        await trade_handler.handle(trade_command)
