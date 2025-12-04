"""Tests para TaskLeaveClan."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.tasks.clan.task_leave_clan import TaskLeaveClan


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.connection = MagicMock()
    sender.connection.address = ("127.0.0.1", 12345)
    return sender


@pytest.fixture
def mock_handler() -> MagicMock:
    """Mock de LeaveClanCommandHandler."""
    handler = MagicMock()
    handler.handle = AsyncMock(
        return_value=CommandResult(success=True, data={"message": "Abandonaste el clan"})
    )
    handler.user_id = 0
    return handler


@pytest.mark.asyncio
async def test_leave_clan_success(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test salir del clan exitosamente."""
    session = {"user_id": 1}

    task = TaskLeaveClan(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # Verificar que se actualizó el user_id en el handler
    assert mock_handler.user_id == 1

    # Verificar que se llamó al handler
    mock_handler.handle.assert_called_once()

    # Verificar mensaje de éxito
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "Abandonaste el clan" in msg


@pytest.mark.asyncio
async def test_leave_clan_no_user_id(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test salir del clan sin user_id en sesión."""
    session: dict[str, int] = {}

    task = TaskLeaveClan(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # No debe llamar al handler
    mock_handler.handle.assert_not_called()

    # Debe enviar mensaje de error
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "logueado" in msg.lower()


@pytest.mark.asyncio
async def test_leave_clan_no_handler(
    mock_message_sender: MagicMock,
) -> None:
    """Test salir del clan sin handler disponible."""
    session = {"user_id": 1}

    task = TaskLeaveClan(b"\x00", mock_message_sender, None, session)
    await task.execute()

    # Debe enviar mensaje de servicio no disponible
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "Servicio no disponible" in msg


@pytest.mark.asyncio
async def test_leave_clan_handler_error(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test salir del clan cuando el handler retorna error."""
    mock_handler.handle = AsyncMock(
        return_value=CommandResult(success=False, error_message="No perteneces a ningún clan")
    )
    session = {"user_id": 1}

    task = TaskLeaveClan(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # Debe enviar mensaje de error
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "No perteneces a ningún clan" in msg


@pytest.mark.asyncio
async def test_leave_clan_success_no_data(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test salir del clan con resultado exitoso pero sin data."""
    mock_handler.handle = AsyncMock(return_value=CommandResult(success=True, data=None))
    session = {"user_id": 1}

    task = TaskLeaveClan(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # Debe mostrar mensaje por defecto
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "Abandonaste el clan" in msg
