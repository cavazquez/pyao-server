"""Tests para PlayerService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.messaging.message_sender import MessageSender
from src.repositories.player_repository import PlayerRepository
from src.services.player.player_service import PlayerService


@pytest.mark.asyncio
async def test_send_position_creates_default():
    """Verifica que send_position cree posición por defecto si no existe."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del player_repo
    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_position = AsyncMock(return_value=None)
    player_repo.set_position = AsyncMock()

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Crear servicio
    player_service = PlayerService(player_repo, message_sender)

    # Enviar posición
    position = await player_service.send_position(123)

    # Verificar que se creó posición por defecto
    player_repo.set_position.assert_called_once_with(123, 50, 50, 1)

    # Verificar que se devolvió la posición
    assert position == {"x": 50, "y": 50, "map": 1}

    # Verificar que se envió CHANGE_MAP
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_send_position_uses_existing():
    """Verifica que send_position use posición existente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_position = AsyncMock(return_value={"x": 100, "y": 200, "map": 5})

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    player_service = PlayerService(player_repo, message_sender)

    position = await player_service.send_position(123)

    # Verificar que NO se creó nueva posición
    player_repo.set_position.assert_not_called()

    # Verificar que se devolvió la posición existente
    assert position == {"x": 100, "y": 200, "map": 5}

    # Verificar que se envió CHANGE_MAP con el mapa correcto
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_send_stats_creates_default():
    """Verifica que send_stats cree stats por defecto si no existen."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_stats = AsyncMock(return_value=None)
    player_repo.set_stats = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    player_service = PlayerService(player_repo, message_sender)

    stats = await player_service.send_stats(123)

    # Verificar que se crearon stats por defecto
    player_repo.set_stats.assert_called_once()
    call_args = player_repo.set_stats.call_args
    assert call_args.kwargs["user_id"] == 123
    assert call_args.kwargs["max_hp"] == 100
    assert call_args.kwargs["level"] == 1

    # Verificar que se devolvieron los stats
    assert stats["max_hp"] == 100
    assert stats["level"] == 1

    # Verificar que se envió UPDATE_USER_STATS
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_send_attributes_creates_default():
    """Verifica que send_attributes cree atributos por defecto si no existen."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_attributes = AsyncMock(return_value=None)
    player_repo.set_attributes = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    player_service = PlayerService(player_repo, message_sender)

    attributes = await player_service.send_attributes(123)

    # Verificar que se crearon atributos por defecto
    player_repo.set_attributes.assert_called_once()
    call_args = player_repo.set_attributes.call_args
    assert call_args.kwargs["user_id"] == 123
    assert call_args.kwargs["strength"] == 10
    assert call_args.kwargs["agility"] == 10

    # Verificar que se devolvieron los atributos
    assert attributes["strength"] == 10
    assert attributes["agility"] == 10

    # Verificar que NO se envió nada (atributos son on-demand)
    assert writer.write.call_count == 0


@pytest.mark.asyncio
async def test_send_hunger_thirst_creates_default():
    """Verifica que send_hunger_thirst cree valores por defecto si no existen."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)
    player_repo.get_hunger_thirst = AsyncMock(
        side_effect=[
            None,  # Primera llamada: no existe
            {  # Segunda llamada: devolver valores creados
                "max_water": 100,
                "min_water": 100,
                "max_hunger": 100,
                "min_hunger": 100,
            },
        ]
    )
    player_repo.set_hunger_thirst = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    player_service = PlayerService(player_repo, message_sender)

    hunger_thirst = await player_service.send_hunger_thirst(123)

    # Verificar que se crearon valores por defecto
    player_repo.set_hunger_thirst.assert_called_once()

    # Verificar que se devolvieron los valores
    assert hunger_thirst["max_water"] == 100
    assert hunger_thirst["min_hunger"] == 100

    # Verificar que se envió UPDATE_HUNGER_AND_THIRST
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_spawn_character_sends_packet():
    """Verifica que spawn_character envíe el paquete CHARACTER_CREATE con valores por defecto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Sin account_repo, debe usar valores por defecto
    player_service = PlayerService(player_repo, message_sender)

    position = {"x": 50, "y": 50, "map": 1, "heading": 3}

    await player_service.spawn_character(123, "testuser", position)

    # Verificar que se envió CHARACTER_CREATE
    assert writer.write.call_count == 1
    sent_packet = writer.write.call_args[0][0]
    # Verificar que usa valores por defecto: body=1, head=1
    assert sent_packet[3] == 1  # body
    assert sent_packet[5] == 1  # head


@pytest.mark.asyncio
async def test_spawn_character_reads_from_redis():
    """Verifica que spawn_character lea body y head desde Redis."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    player_repo = MagicMock(spec=PlayerRepository)

    # Mock de AccountRepository
    account_repo = MagicMock()
    account_repo.get_account = AsyncMock(
        return_value={
            "char_race": "5",  # body
            "char_head": "10",  # head
        }
    )

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Con account_repo, debe leer desde Redis
    player_service = PlayerService(player_repo, message_sender, account_repo)

    position = {"x": 50, "y": 50, "map": 1, "heading": 2}

    await player_service.spawn_character(123, "testuser", position)

    # Verificar que se llamó a get_account
    account_repo.get_account.assert_called_once_with("testuser")

    # Verificar que se envió CHARACTER_CREATE con los valores de Redis
    assert writer.write.call_count == 1
    sent_packet = writer.write.call_args[0][0]
    # Verificar que usa valores de Redis: body=5, head=10
    assert sent_packet[3] == 5  # body
    assert sent_packet[5] == 10  # head
