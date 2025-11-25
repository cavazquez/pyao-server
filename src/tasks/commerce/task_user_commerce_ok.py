"""Task para manejar USER_COMMERCE_OK enviado por el cliente."""

import logging
from typing import TYPE_CHECKING

from src.commands.update_player_trade_command import TradeUpdateAction, UpdatePlayerTradeCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.update_player_trade_handler import (
        UpdatePlayerTradeCommandHandler,
    )
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskUserCommerceOk(Task):
    """Marca al jugador como listo para finalizar el intercambio."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        trade_update_handler: UpdatePlayerTradeCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la task de confirmación final del comercio."""
        super().__init__(data, message_sender)
        self.trade_update_handler = trade_update_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Indica que el jugador ha confirmado el intercambio."""
        user_id = SessionManager.get_user_id(self.session_data)
        if not user_id:
            await self.message_sender.send_console_msg("No estás autenticado.", font_color=1)
            return

        if not self.trade_update_handler:
            logger.error("UpdatePlayerTradeCommandHandler no disponible")
            return

        command = UpdatePlayerTradeCommand(
            user_id=user_id,
            action=TradeUpdateAction.READY,
        )
        await self.trade_update_handler.handle(command)
