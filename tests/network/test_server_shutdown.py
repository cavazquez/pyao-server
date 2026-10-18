"""Cierre con sockets reales, operaciones activas y dependencias todavía disponibles."""

import asyncio
import ssl
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server import ArgentumServer


@pytest.mark.asyncio
async def test_stop_closes_tls_handshake_before_handler_is_created() -> None:
    """Un peer que no envía ClientHello no deja sockets ajenos al registro de handlers."""
    server = ArgentumServer(host="127.0.0.1", port=7777)
    server.outgoing_config.shutdown_timeout_seconds = 2
    server.server = await asyncio.start_server(
        server.handle_client,
        "127.0.0.1",
        0,
        ssl=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER),
        ssl_handshake_timeout=30,
    )
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", server.server.sockets[0].getsockname()[1]
    )
    try:
        await asyncio.sleep(0.01)
        assert not server._client_tasks
        assert len(server.server._clients) == 1
        with patch("src.server.close_password_executor", new=AsyncMock()):
            await asyncio.wait_for(server.stop(), 2.2)
        assert not server.server._clients
        assert await asyncio.wait_for(reader.read(), 0.2) == b""
    finally:
        server.server.abort_clients()
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize("cause", ["transport", "cancellation"])
async def test_disconnect_cleanup_always_releases_lease(cause: str) -> None:
    """Un RST o una cancelación durante la limpieza no retiene la reserva de sesión."""
    server = ArgentumServer()
    reader = asyncio.StreamReader()
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.wait_closed = AsyncMock()
    lease = AsyncMock()
    completed = []

    async def cleanup(*_: object) -> None:
        connection = next(iter(server._connections))
        if cause == "transport":
            connection.close(abort=True)
        else:
            owner = asyncio.current_task()
            assert owner is not None
            owner.cancel()
        await asyncio.sleep(0)
        completed.append(True)

    with patch.object(server, "_cleanup_player", side_effect=cleanup):
        handling = asyncio.create_task(server.handle_client(reader, writer))
        await asyncio.sleep(0)
        assert server._connections
        next(iter(server._connections))._session_lease = lease
        reader.feed_eof()
        await asyncio.gather(handling, return_exceptions=True)
    lease.release.assert_awaited_once()
    assert completed == ([True] if cause == "transport" else [])
    assert not server._client_tasks
    assert not server._connections
    assert server._active_connections == 0


@pytest.mark.asyncio
async def test_stop_drains_active_operation_and_cleanup_before_redis() -> None:  # noqa: PLR0915
    """Stop concurrente conserva el ACK y espera las sesiones antes de cerrar Redis."""
    server = ArgentumServer(host="127.0.0.1", port=7777)
    events = []
    entered, finish = asyncio.Event(), asyncio.Event()
    database = SimpleNamespace(redis=MagicMock(), increment_connections=AsyncMock())

    async def record(label):
        assert "redis" not in events
        events.append(label)

    database.decrement_connections = AsyncMock(side_effect=lambda: record("lease-metrics"))
    database.disconnect = AsyncMock(side_effect=lambda: record("redis"))

    # AsyncMock espera el side effect async, no una función que retorna una coroutine.
    async def metric():
        await record("metrics")

    async def disconnect():
        await record("redis")

    database.decrement_connections = AsyncMock(side_effect=metric)
    database.disconnect = AsyncMock(side_effect=disconnect)
    tick, trades, deaths = AsyncMock(), AsyncMock(), AsyncMock()

    async def cleanup(*_: object):
        await record("pets-and-world")

    async def trade_close():
        assert server._active_connections == 0
        await record("trades")

    async def death_close(**_: object):
        await record("deaths")

    trades.close.side_effect = trade_close
    deaths.close.side_effect = death_close
    server.deps = SimpleNamespace(
        redis_client=database, game_tick=tick, trade_service=trades, player_death_service=deaths
    )

    def create(_packet, sender, _session):
        async def execute():
            entered.set()
            await finish.wait()
            await record("confirmed-operation")
            await sender.send_pong()

        return SimpleNamespace(execute=execute)

    server.server = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    port = server.server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        with (
            patch.object(server, "create_task", side_effect=create),
            patch.object(server, "_cleanup_player", side_effect=cleanup),
            patch("src.server.close_password_executor", new=AsyncMock()),
        ):
            writer.write(bytes([119]))
            await writer.drain()
            await asyncio.wait_for(entered.wait(), 1)
            first = asyncio.create_task(server.stop())
            await asyncio.sleep(0)
            assert not first.done()
            finish.set()
            await asyncio.wait_for(asyncio.gather(first, server.stop()), 2)
            assert await reader.read() == bytes([88])
            await server.stop()
        assert events == [
            "confirmed-operation",
            "pets-and-world",
            "metrics",
            "trades",
            "deaths",
            "redis",
        ]
        database.disconnect.assert_awaited_once()
        assert server._active_connections == 0
        assert not server._client_tasks
        assert not server._connections
        assert not server._receivers
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_stop_cancels_stalled_operation_within_total_deadline() -> None:
    """Un handler detenido se cancela y sus sockets se cierran con plazo finito."""
    server = ArgentumServer(host="127.0.0.1", port=7777)
    server.outgoing_config.shutdown_timeout_seconds = 2
    server.outgoing_config.shutdown_drain_seconds = 0.1
    entered, cancelled = asyncio.Event(), asyncio.Event()

    def create(*_: object):
        async def execute():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        return SimpleNamespace(execute=execute)

    server.server = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    port = server.server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    try:
        with (
            patch.object(server, "create_task", side_effect=create),
            patch("src.server.close_password_executor", new=AsyncMock()),
        ):
            writer.write(bytes([119]))
            await writer.drain()
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.wait_for(server.stop(), 2.2)
        assert cancelled.is_set()
        assert await reader.read() == b""
        assert not server._client_tasks
        assert not server._connections
        assert not server._receivers
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()


@pytest.mark.asyncio
async def test_stop_wakes_idle_authenticated_reader_without_waiting_for_eof() -> None:
    """Cerrar el listener no queda esperando clientes que mantienen abierto TCP."""
    server = ArgentumServer(host="127.0.0.1", port=7777)
    server.server = await asyncio.start_server(server.handle_client, "127.0.0.1", 0)
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", server.server.sockets[0].getsockname()[1]
    )
    try:
        await asyncio.sleep(0.01)
        next(iter(server._connections)).is_authenticated = True
        with patch("src.server.close_password_executor", new=AsyncMock()):
            await asyncio.wait_for(server.stop(), 1)
        assert await reader.read() == b""
        assert not server._client_tasks
        assert not server._receivers
    finally:
        writer.close()
        await writer.wait_closed()
        await server.stop()
