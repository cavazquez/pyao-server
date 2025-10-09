"""Tests para la clase MessageSender."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.packet_id import ServerPacketID


def test_message_sender_initialization() -> None:
    """Verifica que MessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    assert message_sender.connection is connection


@pytest.mark.asyncio
async def test_message_sender_send_dice_roll() -> None:
    """Verifica que send_dice_roll() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    await message_sender.send_dice_roll(
        strength=10,
        agility=12,
        intelligence=14,
        charisma=16,
        constitution=18,
    )

    # Verificar que se llamó write con los datos correctos
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    assert len(written_data) == 6
    assert written_data[0] == ServerPacketID.DICE_ROLL
    assert written_data[1] == 10  # strength
    assert written_data[2] == 12  # agility
    assert written_data[3] == 14  # intelligence
    assert written_data[4] == 16  # charisma
    assert written_data[5] == 18  # constitution

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_message_sender_send_dice_roll_min_values() -> None:
    """Verifica send_dice_roll() con valores mínimos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    await message_sender.send_dice_roll(
        strength=6,
        agility=6,
        intelligence=6,
        charisma=6,
        constitution=6,
    )

    written_data = writer.write.call_args[0][0]
    assert all(written_data[i] == 6 for i in range(1, 6))


@pytest.mark.asyncio
async def test_message_sender_send_dice_roll_max_values() -> None:
    """Verifica send_dice_roll() con valores máximos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    await message_sender.send_dice_roll(
        strength=18,
        agility=18,
        intelligence=18,
        charisma=18,
        constitution=18,
    )

    written_data = writer.write.call_args[0][0]
    assert all(written_data[i] == 18 for i in range(1, 6))


@pytest.mark.asyncio
async def test_message_sender_multiple_sends() -> None:
    """Verifica que se puedan enviar múltiples mensajes."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    await message_sender.send_dice_roll(
        strength=10,
        agility=10,
        intelligence=10,
        charisma=10,
        constitution=10,
    )
    await message_sender.send_dice_roll(
        strength=15,
        agility=15,
        intelligence=15,
        charisma=15,
        constitution=15,
    )

    assert writer.write.call_count == 2
    assert writer.drain.call_count == 2


@pytest.mark.asyncio
async def test_message_sender_uses_connection_send() -> None:
    """Verifica que MessageSender use el método send() de ClientConnection."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    message_sender = MessageSender(connection)

    await message_sender.send_dice_roll(
        strength=12,
        agility=12,
        intelligence=12,
        charisma=12,
        constitution=12,
    )

    # Verificar que se llamó al writer.write (método interno de send)
    assert writer.write.called
    call_args = writer.write.call_args[0][0]
    assert isinstance(call_args, bytes)
    assert len(call_args) == 6
    writer.drain.assert_called_once()
