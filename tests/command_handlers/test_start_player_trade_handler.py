"""Tests para StartPlayerTradeCommandHandler."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.start_player_trade_handler import StartPlayerTradeCommandHandler
from src.commands.start_player_trade_command import StartPlayerTradeCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_trade_service() -> MagicMock:
    """Mock de TradeService."""
    return MagicMock()


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_start_trade_success(
    mock_trade_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test iniciar comercio exitoso."""
    mock_trade_service.request_trade = AsyncMock(return_value=(True, "Comercio iniciado"))

    handler = StartPlayerTradeCommandHandler(
        trade_service=mock_trade_service,
        message_sender=mock_message_sender,
    )
    command = StartPlayerTradeCommand(initiator_id=1, target_username="TargetUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["success"] is True
    assert result.data["message"] == "Comercio iniciado"
    mock_trade_service.request_trade.assert_called_once_with(
        initiator_id=1,
        target_username="TargetUser",
    )
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_start_trade_failure(
    mock_trade_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test iniciar comercio fallido."""
    mock_trade_service.request_trade = AsyncMock(return_value=(False, "Jugador no encontrado"))

    handler = StartPlayerTradeCommandHandler(
        trade_service=mock_trade_service,
        message_sender=mock_message_sender,
    )
    command = StartPlayerTradeCommand(initiator_id=1, target_username="TargetUser")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["success"] is False
    assert "encontrado" in result.data["message"]


@pytest.mark.asyncio
async def test_handle_no_trade_service(mock_message_sender: MagicMock) -> None:
    """Test cuando TradeService no está disponible."""
    handler = StartPlayerTradeCommandHandler(
        trade_service=None,
        message_sender=mock_message_sender,
    )
    command = StartPlayerTradeCommand(initiator_id=1, target_username="TargetUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "TradeService no disponible" in result.error_message
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_trade_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = StartPlayerTradeCommandHandler(
        trade_service=mock_trade_service,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_error_handling(
    mock_trade_service: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores."""
    mock_trade_service.request_trade = AsyncMock(side_effect=Exception("Error"))

    handler = StartPlayerTradeCommandHandler(
        trade_service=mock_trade_service,
        message_sender=mock_message_sender,
    )
    command = StartPlayerTradeCommand(initiator_id=1, target_username="TargetUser")
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
    mock_message_sender.send_console_msg.assert_called()
