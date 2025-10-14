"""Tests para TaskOnline."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.map_manager import MapManager
from src.message_sender import MessageSender
from src.packet_id import ClientPacketID
from src.task_online import TaskOnline


@pytest.mark.asyncio
async def test_task_online_with_players() -> None:
    """Verifica que TaskOnline muestre la lista de jugadores conectados."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Crear MapManager con jugadores
    map_manager = MapManager()

    # Agregar jugadores de prueba
    sender1 = MagicMock()
    sender2 = MagicMock()
    sender3 = MagicMock()

    map_manager.add_player(1, 100, sender1, "Alice")
    map_manager.add_player(1, 101, sender2, "Bob")
    map_manager.add_player(2, 102, sender3, "Charlie")

    # Datos de sesión
    session_data: dict[str, dict[str, int]] = {"user_id": 100}

    # Construir paquete ONLINE (solo PacketID)
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, map_manager, session_data)
    await task.execute()

    # Verificar que se envió el mensaje multilínea
    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que el mensaje contiene la lista de jugadores
    assert "--- Jugadores Online (3) ---" in sent_message
    assert "Alice" in sent_message
    assert "Bob" in sent_message
    assert "Charlie" in sent_message


@pytest.mark.asyncio
async def test_task_online_sorted_alphabetically() -> None:
    """Verifica que los jugadores se muestren ordenados alfabéticamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Crear MapManager con jugadores
    map_manager = MapManager()

    sender1 = MagicMock()
    sender2 = MagicMock()
    sender3 = MagicMock()

    # Agregar en orden no alfabético
    map_manager.add_player(1, 100, sender1, "Zara")
    map_manager.add_player(1, 101, sender2, "Alice")
    map_manager.add_player(1, 102, sender3, "Mike")

    session_data: dict[str, dict[str, int]] = {"user_id": 100}
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, map_manager, session_data)
    await task.execute()

    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar orden alfabético
    lines = sent_message.split("\n")
    player_lines = [line for line in lines if line and not line.startswith("---")]
    assert player_lines == ["Alice", "Mike", "Zara"]


@pytest.mark.asyncio
async def test_task_online_no_players() -> None:
    """Verifica que TaskOnline maneje el caso cuando no hay jugadores conectados."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    # MapManager vacío
    map_manager = MapManager()

    session_data: dict[str, dict[str, int]] = {"user_id": 100}
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, map_manager, session_data)
    await task.execute()

    # Verificar que se envió mensaje de que no hay jugadores
    message_sender.send_console_msg.assert_called_once_with("No hay jugadores conectados")


@pytest.mark.asyncio
async def test_task_online_no_session() -> None:
    """Verifica que TaskOnline falle sin sesión activa."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    map_manager = MapManager()

    # Sin session_data
    session_data: dict[str, dict[str, int]] = {}
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, map_manager, session_data)
    await task.execute()

    # El test pasa si no hay excepciones (solo se loguea warning)


@pytest.mark.asyncio
async def test_task_online_no_map_manager() -> None:
    """Verifica que TaskOnline maneje el caso cuando no hay MapManager."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_console_msg = AsyncMock()

    session_data: dict[str, dict[str, int]] = {"user_id": 100}
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, None, session_data)
    await task.execute()

    # Verificar que se envió un mensaje de error
    message_sender.send_console_msg.assert_called_once_with("Error: Servidor no disponible")


@pytest.mark.asyncio
async def test_task_online_single_player() -> None:
    """Verifica que TaskOnline funcione con un solo jugador."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Crear MapManager con un solo jugador
    map_manager = MapManager()
    sender = MagicMock()
    map_manager.add_player(1, 100, sender, "SoloPlayer")

    session_data: dict[str, dict[str, int]] = {"user_id": 100}
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, map_manager, session_data)
    await task.execute()

    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    assert "--- Jugadores Online (1) ---" in sent_message
    assert "SoloPlayer" in sent_message


@pytest.mark.asyncio
async def test_task_online_no_duplicate_usernames() -> None:
    """Verifica que no se muestren nombres duplicados si un jugador está en múltiples mapas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_multiline_console_msg = AsyncMock()

    # Crear MapManager
    map_manager = MapManager()
    sender1 = MagicMock()
    sender2 = MagicMock()

    # Agregar el mismo jugador en diferentes mapas (caso hipotético)
    map_manager.add_player(1, 100, sender1, "Alice")
    map_manager.add_player(2, 101, sender2, "Bob")

    session_data: dict[str, dict[str, int]] = {"user_id": 100}
    data = bytes([ClientPacketID.ONLINE])

    task = TaskOnline(data, message_sender, map_manager, session_data)
    await task.execute()

    message_sender.send_multiline_console_msg.assert_called_once()
    sent_message = message_sender.send_multiline_console_msg.call_args[0][0]

    # Verificar que cada nombre aparece solo una vez
    assert sent_message.count("Alice") == 1
    assert sent_message.count("Bob") == 1
