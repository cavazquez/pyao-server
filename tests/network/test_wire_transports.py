"""El handler productivo aplica el mismo framing y estado por TCP, TLS y WSS."""

import asyncio
import ssl
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from websockets.asyncio.client import connect

from src.network.websocket_transport import start_websocket
from src.security.ssl_manager import SSLManager
from src.server import ArgentumServer


@pytest.fixture(scope="module")
def wire_tls(tmp_path_factory):
    """Genera una CA local efímera; el cliente verifica el certificado y hostname.

    Returns:
        Contextos de ambos extremos, sin modificar el almacén del sistema.
    """
    folder = tmp_path_factory.mktemp("wire-tls")
    manager = SSLManager(
        enabled=True,
        cert_path=None,
        key_path=None,
        default_cert_path=folder / "cert.pem",
        default_key_path=folder / "key.pem",
    )
    manager.prepare()
    return manager.build_context(), ssl.create_default_context(cafile=str(manager.cert_path))


async def stream_roundtrip(port, context, ending, incomplete, finished):
    """Ejercita el socket binario con EOF limpio o rechazo remoto."""
    reader, writer = await asyncio.open_connection("localhost", port, ssl=context)
    try:
        for chunk in (b"\x77", b"\x77" + ending[:1]):
            writer.write(chunk)
            await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(2), 2) == b"\x58\x58"
        if len(ending) > 1:
            writer.write(ending[1:])
            await writer.drain()
        if incomplete:
            writer.close()
        await asyncio.wait_for(finished.wait(), 2)
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["tcp", "tls", "wss"])
@pytest.mark.parametrize(
    ("ending", "incomplete"),
    [
        (b"\xff", False),
        (b"\x03\xff\xff", False),
        (b"\x06\x00", False),
        (b"\x06\x01", False),
        (b"\x03\x05\x00x", True),
    ],
    ids=["unknown-id", "false-length", "invalid-value", "before-login", "partial-eof"],
)
async def test_real_transports_fragment_coalesce_and_reject_without_dispatch(
    transport, ending, incomplete, wire_tls
):
    """Dos PING válidos sobreviven fragmentación; el mensaje inválido no se ejecuta."""
    server = ArgentumServer()
    received, finished = [], asyncio.Event()

    def create(data, sender, _session):
        async def execute():
            received.append(data)
            await sender.connection.send(b"\x58")

        return SimpleNamespace(execute=execute)

    async def handle(reader, writer):
        try:
            await server.handle_client(reader, writer)
        finally:
            finished.set()

    server_context, client_context = wire_tls
    listener = (
        await start_websocket(handle, "127.0.0.1", 0, ["https://example.invalid"], server_context)
        if transport == "wss"
        else await asyncio.start_server(
            handle, "127.0.0.1", 0, ssl=server_context if transport == "tls" else None
        )
    )
    port = listener.sockets[0].getsockname()[1]
    try:
        with patch.object(server, "create_task", side_effect=create):
            if transport == "wss":
                async with connect(
                    f"wss://localhost:{port}",
                    origin="https://example.invalid",
                    ssl=client_context,
                ) as peer:
                    await peer.send(b"\x77")
                    await peer.send(b"\x77" + ending[:1])
                    replies = b""
                    while len(replies) < 2:
                        replies += await asyncio.wait_for(peer.recv(), 2)
                    assert replies == b"\x58\x58"
                    if len(ending) > 1:
                        await peer.send(ending[1:])
                    if incomplete:
                        await peer.close()
                    await asyncio.wait_for(finished.wait(), 2)
            else:
                await stream_roundtrip(
                    port,
                    client_context if transport == "tls" else None,
                    ending,
                    incomplete,
                    finished,
                )
    finally:
        listener.close()
        await listener.wait_closed()
    assert received == [b"\x77", b"\x77"]
    assert server._active_connections == 0
    assert not server._connections
