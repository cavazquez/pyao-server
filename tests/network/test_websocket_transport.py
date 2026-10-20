"""El puente binario respeta origen, fragmentación, límites y cierre de sesión."""

import asyncio

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError, InvalidStatus

from src.network.websocket_transport import start_websocket


@pytest.mark.asyncio
async def test_binary_messages_share_one_stream_and_close_cleanly():
    """Separar mensajes WSS no cambia el flujo de bytes AO visto por el handler."""
    completed = asyncio.Event()

    async def echo(reader, writer):
        assert await reader.readexactly(6) == b"abcdef"
        writer.write(b"reply")
        await writer.drain()
        assert await reader.read() == b""
        completed.set()

    listener = await start_websocket(
        echo, "127.0.0.1", 0, ["https://example.invalid"], None, tls_proxy=True
    )
    try:
        port = listener.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}", origin="https://example.invalid") as peer:
            await peer.send(b"ab")
            await peer.send(b"cdef")
            assert await peer.recv() == b"reply"
        await asyncio.wait_for(completed.wait(), 2)
    finally:
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_rejects_wrong_origin_and_text_messages():
    """El endpoint no acepta sitios ajenos ni mensajes que eludan el framer binario."""

    async def drain(reader, _writer):
        await reader.read()

    listener = await start_websocket(
        drain, "127.0.0.1", 0, ["https://example.invalid"], None, tls_proxy=True
    )
    try:
        port = listener.sockets[0].getsockname()[1]
        with pytest.raises(InvalidStatus, match="403"):
            async with connect(f"ws://127.0.0.1:{port}", origin="https://other.invalid"):
                pass
        async with connect(f"ws://127.0.0.1:{port}", origin="https://example.invalid") as peer:
            await peer.send("forbidden")
            with pytest.raises(ConnectionClosedError, match="1003"):
                await peer.recv()
    finally:
        listener.close()
        await listener.wait_closed()


@pytest.mark.asyncio
async def test_proxy_and_origin_policy_fail_closed():
    """Un backend WS sin TLS no se expone accidentalmente fuera de loopback."""

    async def noop(_reader, _writer):
        pass

    for host, origins, proxy in (
        ("127.0.0.1", [], True),
        ("0.0.0.0", ["https://example.invalid"], True),
        ("127.0.0.1", ["https://example.invalid"], False),
    ):
        with pytest.raises(ValueError, match="WSS requiere"):
            await start_websocket(noop, host, 0, origins, None, tls_proxy=proxy)
