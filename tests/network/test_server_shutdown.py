"""Cierre con sockets reales, operaciones activas y dependencias todavía disponibles."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server import ArgentumServer


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
