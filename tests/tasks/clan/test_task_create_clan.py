"""Tests para TaskCreateClan."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.tasks.clan.task_create_clan import TaskCreateClan


def _build_packet(clan_name: str, description: str = "") -> bytes:
    """Construye un paquete de crear clan.

    Formato: PacketID (1 byte) + nombre (2 bytes length + string) + descripción opcional
    """
    # PacketReader salta el primer byte asumiendo que es PacketID
    packet = bytes([0x00])  # Dummy PacketID

    name_bytes = clan_name.encode("utf-8")
    packet += len(name_bytes).to_bytes(2, "little") + name_bytes

    if description:
        desc_bytes = description.encode("utf-8")
        packet += len(desc_bytes).to_bytes(2, "little") + desc_bytes

    return packet


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.fixture
def mock_handler() -> MagicMock:
    """Mock de CreateClanCommandHandler."""
    handler = MagicMock()
    handler.handle = AsyncMock(
        return_value=CommandResult(success=True, data={"message": "Clan creado"})
    )
    return handler


@pytest.mark.asyncio
async def test_create_clan_success(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test crear clan exitosamente."""
    data = _build_packet("MiClan", "Una descripción")
    session = {"user_id": 1, "username": "TestUser"}

    task = TaskCreateClan(data, mock_message_sender, mock_handler, session)
    await task.execute()

    # Verificar que se llamó al handler
    mock_handler.handle.assert_called_once()
    call_args = mock_handler.handle.call_args[0][0]
    assert call_args.clan_name == "MiClan"
    assert call_args.description == "Una descripción"

    # Verificar mensaje de éxito
    mock_message_sender.send_console_msg.assert_called_once()
    msg_call = mock_message_sender.send_console_msg.call_args
    assert "Clan creado" in msg_call.args[0]


@pytest.mark.asyncio
async def test_create_clan_no_user_id(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test crear clan sin user_id en sesión."""
    data = _build_packet("MiClan")
    session: dict[str, int] = {}  # Sin user_id

    task = TaskCreateClan(data, mock_message_sender, mock_handler, session)
    await task.execute()

    # No debe llamar al handler
    mock_handler.handle.assert_not_called()

    # Debe enviar mensaje de error
    mock_message_sender.send_console_msg.assert_called_once()
    msg_call = mock_message_sender.send_console_msg.call_args
    assert "No estás autenticado" in msg_call.args[0]


@pytest.mark.asyncio
async def test_create_clan_invalid_packet(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test crear clan con paquete inválido."""
    data = b""  # Paquete vacío
    session = {"user_id": 1}

    task = TaskCreateClan(data, mock_message_sender, mock_handler, session)
    await task.execute()

    # No debe llamar al handler
    mock_handler.handle.assert_not_called()

    # Debe enviar mensaje de formato inválido
    mock_message_sender.send_console_msg.assert_called_once()
    msg_call = mock_message_sender.send_console_msg.call_args
    assert "Formato inválido" in msg_call.args[0]


@pytest.mark.asyncio
async def test_create_clan_no_handler(
    mock_message_sender: MagicMock,
) -> None:
    """Test crear clan sin handler disponible."""
    data = _build_packet("MiClan")
    session = {"user_id": 1}

    task = TaskCreateClan(data, mock_message_sender, None, session)
    await task.execute()

    # Debe enviar mensaje de servicio no disponible
    mock_message_sender.send_console_msg.assert_called_once()
    msg_call = mock_message_sender.send_console_msg.call_args
    assert "Servicio no disponible" in msg_call.args[0]


@pytest.mark.asyncio
async def test_create_clan_handler_error(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test crear clan cuando el handler retorna error."""
    mock_handler.handle = AsyncMock(
        return_value=CommandResult(success=False, error_message="Ya tienes un clan")
    )

    data = _build_packet("MiClan")
    session = {"user_id": 1}

    task = TaskCreateClan(data, mock_message_sender, mock_handler, session)
    await task.execute()

    # Debe enviar mensaje de error
    mock_message_sender.send_console_msg.assert_called_once()
    msg_call = mock_message_sender.send_console_msg.call_args
    assert "Ya tienes un clan" in msg_call.args[0]


@pytest.mark.asyncio
async def test_create_clan_without_description(
    mock_message_sender: MagicMock,
    mock_handler: MagicMock,
) -> None:
    """Test crear clan sin descripción."""
    data = _build_packet("SoloClan")
    session = {"user_id": 1, "username": "TestUser"}

    task = TaskCreateClan(data, mock_message_sender, mock_handler, session)
    await task.execute()

    # Verificar que se llamó al handler con descripción vacía
    mock_handler.handle.assert_called_once()
    call_args = mock_handler.handle.call_args[0][0]
    assert call_args.clan_name == "SoloClan"
    assert not call_args.description


@pytest.mark.asyncio
async def test_parse_packet_valid() -> None:
    """Test parseo de paquete válido."""
    data = _build_packet("TestClan", "Test Description")
    sender = MagicMock()

    task = TaskCreateClan(data, sender, None, {})
    result = task._parse_packet()

    assert result is not None
    assert result[0] == "TestClan"
    assert result[1] == "Test Description"


@pytest.mark.asyncio
async def test_parse_packet_empty_name() -> None:
    """Test parseo de paquete con nombre vacío."""
    # PacketID + longitud 0 para el nombre
    data = b"\x00\x00\x00"
    sender = MagicMock()

    task = TaskCreateClan(data, sender, None, {})
    result = task._parse_packet()

    assert result is None
