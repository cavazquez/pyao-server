"""Tests para InformationCommandHandler."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.information_handler import InformationCommandHandler
from src.commands.information_command import InformationCommand
from src.commands.walk_command import WalkCommand


@pytest.fixture
def mock_server_repo() -> MagicMock:
    """Mock de ServerRepository."""
    repo = MagicMock()
    repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - 3600)
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_all_connected_players = MagicMock(return_value=[1, 2, 3])
    return manager


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.connection = MagicMock()
    sender.connection.address = "127.0.0.1:12345"
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_valid_command(
    mock_server_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando de información válido."""
    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_multiline_console_msg.assert_called_once()
    assert result.data is not None
    assert "message" in result.data


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_server_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    # Pasar un comando de otro tipo
    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False
    assert "inválido" in result.error_message.lower()


@pytest.mark.asyncio
async def test_information_contains_players(
    mock_server_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que la información incluye cantidad de jugadores."""
    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_multiline_console_msg.call_args[0][0]
    assert "Jugadores conectados: 3" in call_args


@pytest.mark.asyncio
async def test_information_contains_uptime(
    mock_server_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test que la información incluye uptime."""
    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_multiline_console_msg.call_args[0][0]
    assert "Uptime:" in call_args


@pytest.mark.asyncio
async def test_information_without_map_manager(
    mock_server_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test información sin MapManager."""
    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=None,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_multiline_console_msg.call_args[0][0]
    assert "Jugadores conectados: N/A" in call_args


@pytest.mark.asyncio
async def test_information_without_server_repo(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test información sin ServerRepository."""
    handler = InformationCommandHandler(
        server_repo=None,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    # No debe incluir uptime si no hay server_repo


@pytest.mark.asyncio
async def test_information_uptime_format_days(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test formato de uptime con días."""
    mock_server_repo = MagicMock()
    # Uptime de 2 días, 3 horas, 30 minutos
    uptime_seconds = (2 * 86400) + (3 * 3600) + (30 * 60)
    mock_server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - uptime_seconds)

    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_multiline_console_msg.call_args[0][0]
    assert "2d" in call_args or "d" in call_args


@pytest.mark.asyncio
async def test_information_uptime_format_hours(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test formato de uptime con horas."""
    mock_server_repo = MagicMock()
    # Uptime de 5 horas, 30 minutos
    uptime_seconds = (5 * 3600) + (30 * 60)
    mock_server_repo.get_uptime_start = AsyncMock(return_value=int(time.time()) - uptime_seconds)

    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    assert result.success is True
    call_args = mock_message_sender.send_multiline_console_msg.call_args[0][0]
    assert "5h" in call_args or "h" in call_args


@pytest.mark.asyncio
async def test_information_error_handling(
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test manejo de errores en información."""
    mock_server_repo = MagicMock()
    mock_server_repo.get_uptime_start = AsyncMock(side_effect=Exception("Error"))

    handler = InformationCommandHandler(
        server_repo=mock_server_repo,
        map_manager=mock_map_manager,
        message_sender=mock_message_sender,
    )

    command = InformationCommand()
    result = await handler.handle(command)

    # Debe manejar el error y retornar error result
    assert result.success is False
    assert "error" in result.error_message.lower()
