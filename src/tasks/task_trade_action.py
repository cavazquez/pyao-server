"""Acciones versionadas del intercambio, exclusivamente después de negociar el bit 128."""

import re
import struct
from typing import TYPE_CHECKING

from src.network.capabilities import Capability
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.trade_service import TradeService


TRADE_ACTION_BYTES = 46
SESSION_ID_BYTES = 32


class TaskTradeAction(Task):
    """No acepta acciones clásicas como confirmación de una revisión nueva."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        trade_service: TradeService,
        session_data: dict[str, dict[str, int] | int] | None = None,
    ) -> None:
        """Recibe la sesión autenticada mediante la factory habitual."""
        super().__init__(data, message_sender)
        self.trade_service = trade_service
        self.session_data = session_data if session_data is not None else {}

    async def execute(self) -> None:
        """Descarta extensiones no autorizadas y valida la estructura antes del servicio."""
        connection = self.message_sender.connection
        user_id = SessionManager.get_user_id(self.session_data)
        if (
            not connection.is_authenticated
            or not user_id
            or len(self.data) != TRADE_ACTION_BYTES
            or not connection.capabilities.enabled & Capability.TRADE_STATE
            or self.trade_service.map_manager.get_player_message_sender(user_id)
            is not self.message_sender
        ):
            return
        _, version, size, raw_id, revision, action, slot, quantity = struct.unpack(
            "<BBH32siBBi", self.data
        )
        if version != 1 or size != SESSION_ID_BYTES or not re.fullmatch(rb"[0-9a-f]{32}", raw_id):
            return
        success, message = await self.trade_service.apply_action(
            user_id, raw_id.decode("ascii"), revision, action, slot, quantity
        )
        if not success:
            await self.trade_service.resend_state(user_id, message)
            await self.message_sender.send_console_msg(message, font_color=1)
