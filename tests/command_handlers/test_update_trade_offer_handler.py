"""Tests for UpdateTradeOfferCommandHandler."""

from unittest.mock import AsyncMock

import pytest

from src.command_handlers.update_trade_offer_handler import UpdateTradeOfferCommandHandler
from src.commands.update_trade_offer_command import UpdateTradeOfferCommand


@pytest.mark.asyncio
async def test_handle_updates_offer() -> None:
    """Delegates to TradeService and relays message."""
    trade_service = AsyncMock()
    trade_service.update_offer = AsyncMock(return_value=(True, "OK"))
    message_sender = AsyncMock()

    handler = UpdateTradeOfferCommandHandler(trade_service, message_sender)
    command = UpdateTradeOfferCommand(user_id=1, slot=2, quantity=3)

    result = await handler.handle(command)

    trade_service.update_offer.assert_awaited_with(user_id=1, slot=2, quantity=3)
    message_sender.send_console_msg.assert_awaited_with("OK", font_color=7)
    assert result.success is True


@pytest.mark.asyncio
async def test_handle_without_trade_service() -> None:
    """Notifies user when TradeService is missing."""
    message_sender = AsyncMock()
    handler = UpdateTradeOfferCommandHandler(None, message_sender)
    command = UpdateTradeOfferCommand(user_id=1, slot=2, quantity=3)

    result = await handler.handle(command)

    assert result.success is False
    message_sender.send_console_msg.assert_awaited()

