"""Tests para la clase ClientConnection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.client_connection import ClientConnection
from src.packet_id import ServerPacketID


def test_client_connection_initialization() -> None:
    """Verifica que ClientConnection se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    connection = ClientConnection(writer)
    assert connection.writer is writer
    assert connection.address == ("192.168.1.100", 54321)
    writer.get_extra_info.assert_called_once_with("peername")


@pytest.mark.asyncio
async def test_client_connection_send() -> None:
    """Verifica que send() escriba datos y llame a drain()."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)
    data = b"\x01\x02\x03\x04"

    await connection.send(data)

    writer.write.assert_called_once_with(data)
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_client_connection_send_empty_data() -> None:
    """Verifica que send() funcione con datos vacíos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)

    await connection.send(b"")

    writer.write.assert_called_once_with(b"")
    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_client_connection_send_dice_roll() -> None:
    """Verifica que send_dice_roll() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)

    await connection.send_dice_roll(
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
async def test_client_connection_send_dice_roll_min_values() -> None:
    """Verifica send_dice_roll() con valores mínimos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)

    await connection.send_dice_roll(
        strength=6,
        agility=6,
        intelligence=6,
        charisma=6,
        constitution=6,
    )

    written_data = writer.write.call_args[0][0]
    assert all(written_data[i] == 6 for i in range(1, 6))


@pytest.mark.asyncio
async def test_client_connection_send_dice_roll_max_values() -> None:
    """Verifica send_dice_roll() con valores máximos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)

    await connection.send_dice_roll(
        strength=18,
        agility=18,
        intelligence=18,
        charisma=18,
        constitution=18,
    )

    written_data = writer.write.call_args[0][0]
    assert all(written_data[i] == 18 for i in range(1, 6))


def test_client_connection_close() -> None:
    """Verifica que close() cierre el writer."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)

    connection = ClientConnection(writer)
    connection.close()

    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_client_connection_wait_closed() -> None:
    """Verifica que wait_closed() espere al cierre del writer."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.wait_closed = AsyncMock()

    connection = ClientConnection(writer)
    await connection.wait_closed()

    writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_client_connection_multiple_sends() -> None:
    """Verifica que se puedan enviar múltiples mensajes."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    connection = ClientConnection(writer)

    await connection.send(b"\x01\x02")
    await connection.send(b"\x03\x04")
    await connection.send(b"\x05\x06")

    assert writer.write.call_count == 3
    assert writer.drain.call_count == 3
