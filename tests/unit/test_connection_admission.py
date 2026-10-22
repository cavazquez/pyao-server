"""Admisión por proceso y liberación de plazas en todos los caminos de salida."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.server import ArgentumServer


def make_writer():
    """Crea un transporte sintético que admite cierre async."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.wait_closed = AsyncMock()
    return writer


@pytest.mark.asyncio
async def test_burst_admits_only_configured_capacity():
    """La ráfaga excedente no crea sender, sesión ni servicios de aplicación."""
    with patch(
        "src.server.config_manager.get",
        side_effect=lambda key, default: 2 if key == "server.max_connections" else default,
    ):
        server = ArgentumServer()
    entered = asyncio.Event()
    release = asyncio.Event()
    reads = 0

    async def read(_max_bytes):
        nonlocal reads
        reads += 1
        if reads == 2:
            entered.set()
        await release.wait()
        return b""

    readers = [MagicMock(read=AsyncMock(side_effect=read)) for _ in range(12)]
    writers = [make_writer() for _ in readers]
    with patch("src.server.MessageSender") as sender:
        tasks = [
            asyncio.create_task(server.handle_client(r, w))
            for r, w in zip(readers, writers, strict=True)
        ]
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert server._active_connections == 2
        assert sender.call_count == 2
        assert sum(w.close.called for w in writers) == 10
        release.set()
        await asyncio.gather(*tasks)
    assert server._active_connections == 0
    assert all(w.close.call_count == 1 for w in writers)
    later = make_writer()
    await server.handle_client(MagicMock(read=AsyncMock(return_value=b"")), later)
    assert server._active_connections == 0
    later.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["redis", "handler", "cleanup", "cancel"])
async def test_failure_or_cancellation_always_releases_place(failure):
    """Ni errores previos al login ni cancelación dejan plazas o métricas negativas."""
    server = ArgentumServer()
    server.max_connections = 1
    server.deps = MagicMock()
    server.deps.redis_client.redis.hget = AsyncMock(return_value=None)
    server.deps.redis_client.increment_connections = AsyncMock()
    server.deps.redis_client.decrement_connections = AsyncMock()
    reader = MagicMock(read=AsyncMock(return_value=b"\x01"))
    writer = make_writer()
    if failure == "redis":
        server.deps.redis_client.increment_connections.side_effect = ConnectionError
    if failure == "cancel":
        reader.read.side_effect = asyncio.CancelledError
    task = MagicMock(execute=AsyncMock(side_effect=ValueError("Sintético")))
    with (
        patch.object(server, "create_task", return_value=task),
        patch.object(
            server,
            "_cleanup_player",
            AsyncMock(side_effect=RuntimeError if failure == "cleanup" else None),
        ),
    ):
        if failure == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await server.handle_client(reader, writer)
        else:
            await server.handle_client(reader, writer)
    assert server._active_connections == 0
    writer.close.assert_called_once()
    assert server.deps.redis_client.decrement_connections.await_count == (
        0 if failure == "redis" else 1
    )
