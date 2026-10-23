"""Ejercita handle_client y ClientConnection reales con lecturas TCP adversas."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server import ArgentumServer


def writer() -> MagicMock:
    """Crea sólo el extremo de salida; ClientConnection conserva su implementación."""
    value = MagicMock()
    value.get_extra_info.return_value = ("127.0.0.1", 12345)
    value.wait_closed = AsyncMock()
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize("fragmented", [False, True])
async def test_handle_client_dispatches_complete_packets_once_in_order(fragmented: bool) -> None:
    """Dos WALK y DOUBLE_CLICK se entregan igual agrupados o byte a byte."""
    server = ArgentumServer()
    reader = asyncio.StreamReader()
    expected = [b"\x06\x01", b"\x06\x02", b"\x1b\x32\x33", b"\x0a"]
    received = []
    completed = asyncio.Event()

    def create(data, _sender, _session):
        async def execute():
            received.append(data)
            if len(received) == len(expected):
                completed.set()

        return MagicMock(execute=execute)

    output = writer()
    with (
        patch.object(server, "create_task", side_effect=create),
        patch.object(server, "_validate_packet_state"),
    ):
        handling = asyncio.create_task(server.handle_client(reader, output))
        payload = b"".join(expected)
        chunks = [bytes([value]) for value in payload] if fragmented else [payload]
        for chunk in chunks:
            reader.feed_data(chunk)
            await asyncio.sleep(0)
        await asyncio.wait_for(completed.wait(), timeout=1)
        reader.feed_eof()
        await handling
    assert received == expected
    assert server._active_connections == 0
    output.close.assert_called_once()


@pytest.mark.asyncio
async def test_connections_keep_independent_partial_buffers_and_ignore_partial_eof() -> None:
    """El segundo cliente no completa el WALK incompleto del primero."""
    server = ArgentumServer()
    readers = [asyncio.StreamReader(), asyncio.StreamReader()]
    received = []
    task = MagicMock(execute=AsyncMock())

    def create(data, _sender, _session):
        received.append(data)
        return task

    with (
        patch.object(server, "create_task", side_effect=create),
        patch.object(server, "_validate_packet_state"),
    ):
        handling = [asyncio.create_task(server.handle_client(r, writer())) for r in readers]
        readers[0].feed_data(b"\x06")
        readers[1].feed_data(b"\x06\x04")
        for reader in readers:
            reader.feed_eof()
        await asyncio.gather(*handling)
    assert received == [b"\x06\x04"]
    task.execute.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"\xff", b"\x03\xff\xff", b"\x7a\xff"])
async def test_runtime_closes_invalid_framing_without_dispatch(payload: bytes) -> None:
    """IDs, longitudes y subcomandos inválidos cierran el transporte inmediatamente."""
    server = ArgentumServer()
    reader = asyncio.StreamReader()
    reader.feed_data(payload)
    output = writer()
    with patch.object(server, "create_task") as create:
        await asyncio.wait_for(server.handle_client(reader, output), timeout=1)
    create.assert_not_called()
    output.close.assert_called_once()
