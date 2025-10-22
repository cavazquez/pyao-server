"""Tests para la clase ClientConnection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection


def test_client_connection_initialization() -> None:
    """Verifica que ClientConnection se inicialice correctamente."""
    reader = MagicMock()
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    connection = ClientConnection(reader, writer)
    assert connection.reader is reader
    assert connection.writer is writer
    assert connection.address == ("192.168.1.100", 54321)
    writer.get_extra_info.assert_called_once_with("peername")


@pytest.mark.asyncio
async def test_client_connection_send() -> None:
    """Verifica que send() escriba datos y llame a drain()."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
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

    reader = MagicMock()
    connection = ClientConnection(reader, writer)

    await connection.send(b"")

    writer.write.assert_called_once_with(b"")
    writer.drain.assert_called_once()


def test_client_connection_close() -> None:
    """Verifica que close() cierre el writer."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    connection.close()

    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_client_connection_wait_closed() -> None:
    """Verifica que wait_closed() espere al cierre del writer."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.wait_closed = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    await connection.wait_closed()

    writer.wait_closed.assert_called_once()


@pytest.mark.asyncio
async def test_client_connection_multiple_sends() -> None:
    """Verifica que se puedan enviar múltiples mensajes."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)

    await connection.send(b"\x01\x02")
    await connection.send(b"\x03\x04")
    await connection.send(b"\x05\x06")

    assert writer.write.call_count == 3
    assert writer.drain.call_count == 3
