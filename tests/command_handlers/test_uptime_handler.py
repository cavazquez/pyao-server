"""Tests para UptimeCommandHandler."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.uptime_handler import UptimeCommandHandler
from src.commands.uptime_command import UptimeCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_server_repo() -> MagicMock:
    """Mock de ServerRepository."""
    repo = MagicMock()
    repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - 3600)
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_valid_command(
    mock_server_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando de uptime válido."""
    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_console_msg.assert_called_once()
    assert result.data is not None
    assert "message" in result.data


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_server_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    # Pasar un comando de otro tipo
    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_uptime_format_with_days(
    mock_message_sender: MagicMock,
) -> None:
    """Test formato de uptime con días."""
    mock_server_repo = MagicMock()
    # Uptime de 2 días, 3 horas, 30 minutos, 45 segundos
    uptime_seconds = (2 * 86400) + (3 * 3600) + (30 * 60) + 45
    mock_server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - uptime_seconds)

    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "dia" in call_args.lower() or "dias" in call_args.lower()


@pytest.mark.asyncio
async def test_uptime_format_with_hours(
    mock_message_sender: MagicMock,
) -> None:
    """Test formato de uptime con horas."""
    mock_server_repo = MagicMock()
    # Uptime de 5 horas, 30 minutos, 15 segundos
    uptime_seconds = (5 * 3600) + (30 * 60) + 15
    mock_server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - uptime_seconds)

    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "hora" in call_args.lower() or "horas" in call_args.lower()


@pytest.mark.asyncio
async def test_uptime_format_with_minutes(
    mock_message_sender: MagicMock,
) -> None:
    """Test formato de uptime con minutos."""
    mock_server_repo = MagicMock()
    # Uptime de 45 minutos, 30 segundos
    uptime_seconds = (45 * 60) + 30
    mock_server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - uptime_seconds)

    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "minuto" in call_args.lower() or "minutos" in call_args.lower()


@pytest.mark.asyncio
async def test_uptime_format_seconds_only(
    mock_message_sender: MagicMock,
) -> None:
    """Test formato de uptime solo con segundos."""
    mock_server_repo = MagicMock()
    # Uptime de solo 45 segundos
    mock_server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - 45)

    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "segundo" in call_args.lower() or "segundos" in call_args.lower()


@pytest.mark.asyncio
async def test_uptime_without_server_repo(
    mock_message_sender: MagicMock,
) -> None:
    """Test uptime sin ServerRepository."""
    handler = UptimeCommandHandler(
        server_repo=None,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "no disponible" in call_args.lower()


@pytest.mark.asyncio
async def test_uptime_no_start_time(
    mock_message_sender: MagicMock,
) -> None:
    """Test uptime cuando no hay start_time."""
    mock_server_repo = MagicMock()
    mock_server_repo.get_uptime_start = AsyncMock(return_value=None)

    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_console_msg.call_args[0][0]
    assert "no se pudo obtener" in call_args.lower()


@pytest.mark.asyncio
async def test_uptime_error_handling(
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores en uptime."""
    mock_server_repo = MagicMock()
    mock_server_repo.get_uptime_start = AsyncMock(side_effect=Exception("Error"))

    handler = UptimeCommandHandler(
        server_repo=mock_server_repo,
        message_sender=mock_message_sender,
    )

    command = UptimeCommand()
    result = await handler.handle(command)

    assert result.success is False
    assert "error" in result.error_message.lower()
