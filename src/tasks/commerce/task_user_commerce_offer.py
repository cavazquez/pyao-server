"""Task para manejar el packet USER_COMMERCE_OFFER."""

import logging
from typing import TYPE_CHECKING

from src.commands.update_trade_offer_command import UpdateTradeOfferCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.update_trade_offer_handler import UpdateTradeOfferCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskUserCommerceOffer(Task):
    """Actualiza la oferta del jugador durante un comercio."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        trade_offer_handler: UpdateTradeOfferCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la task de oferta."""
        super().__init__(data, message_sender)
        self.trade_offer_handler = trade_offer_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el cambio de oferta del jugador."""
        user_id = SessionManager.get_user_id(self.session_data)
        if not user_id:
            await self.message_sender.send_console_msg("Sesión inválida.", font_color=1)
            return

        if not self.trade_offer_handler:
            logger.error("UpdateTradeOfferCommandHandler no disponible")
            return

        reader = PacketReader(self.data)
        slot = reader.read_byte()
        quantity = reader.read_int16()

        command = UpdateTradeOfferCommand(user_id=user_id, slot=slot, quantity=quantity)
        await self.trade_offer_handler.handle(command)
