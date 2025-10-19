"""Tests para la clase MessageSender.

Estos tests verifican la funcionalidad core de MessageSender que no está
cubierta por los componentes especializados (ConsoleMessageSender, etc.).

Los tests de métodos específicos (send_console_msg, send_play_midi, etc.)
están en los tests de sus respectivos componentes.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.packet_id import ServerPacketID


def test_message_sender_initialization() -> None:
    """Verifica que MessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    assert message_sender.connection is connection


@pytest.mark.asyncio
async def test_message_sender_send_dice_roll() -> None:
    """Verifica que send_dice_roll() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
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
async def test_message_sender_send_logged() -> None:
    """Verifica que send_logged() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    user_class = 5
    await message_sender.send_logged(user_class)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + userClass
    assert len(written_data) == 2
    assert written_data[0] == ServerPacketID.LOGGED
    assert written_data[1] == user_class

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_message_sender_multiple_sends() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    await message_sender.send_dice_roll(
        strength=10,
        agility=10,
        intelligence=10,
        charisma=10,
        constitution=10,
    )
    await message_sender.send_logged(5)

    assert writer.write.call_count == 2
    assert writer.drain.call_count == 2
