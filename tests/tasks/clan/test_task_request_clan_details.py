"""Tests para TaskRequestClanDetails."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.tasks.clan.task_request_clan_details import TaskRequestClanDetails


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
    """Mock de RequestClanDetailsCommandHandler."""
    handler = MagicMock()
    handler.handle = AsyncMock(return_value=CommandResult(success=True))
    handler.user_id = 0
    return handler


@pytest.mark.asyncio
async def test_request_clan_details_success(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test solicitar detalles del clan exitosamente."""
    session = {"user_id": 1}

    task = TaskRequestClanDetails(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # Verificar que se actualizó el user_id en el handler
    assert mock_handler.user_id == 1

    # Verificar que se llamó al handler
    mock_handler.handle.assert_called_once()

    # No debe mostrar mensaje (el handler envía los datos directamente)
    mock_message_sender.send_console_msg.assert_not_called()


@pytest.mark.asyncio
async def test_request_clan_details_no_user_id(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test solicitar detalles sin user_id en sesión."""
    session: dict[str, int] = {}

    task = TaskRequestClanDetails(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # No debe llamar al handler
    mock_handler.handle.assert_not_called()

    # Debe enviar mensaje de error
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "logueado" in msg.lower()


@pytest.mark.asyncio
async def test_request_clan_details_no_handler(
    mock_message_sender: MagicMock,
) -> None:
    """Test solicitar detalles sin handler disponible."""
    session = {"user_id": 1}

    task = TaskRequestClanDetails(b"\x00", mock_message_sender, None, session)
    await task.execute()

    # Debe enviar mensaje de servicio no disponible
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "Servicio no disponible" in msg


@pytest.mark.asyncio
async def test_request_clan_details_handler_error(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test cuando el handler retorna error."""
    mock_handler.handle = AsyncMock(
        return_value=CommandResult(success=False, error_message="No tienes un clan")
    )
    session = {"user_id": 1}

    task = TaskRequestClanDetails(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # Debe enviar mensaje de error
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "No tienes un clan" in msg


@pytest.mark.asyncio
async def test_request_clan_details_error_no_message(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test error sin mensaje específico."""
    mock_handler.handle = AsyncMock(return_value=CommandResult(success=False, error_message=None))
    session = {"user_id": 1}

    task = TaskRequestClanDetails(b"\x00", mock_message_sender, mock_handler, session)
    await task.execute()

    # Debe mostrar mensaje de error por defecto
    mock_message_sender.send_console_msg.assert_called_once()
    msg = mock_message_sender.send_console_msg.call_args.args[0]
    assert "Error al obtener detalles" in msg
