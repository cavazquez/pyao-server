"""Un destinatario bloqueado no frena broadcasts ni retiene memoria ilimitada."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService


def peer(**limits: object):
    """Crea un transporte con awaitables controlables y una conexión real."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 1234)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return ClientConnection(MagicMock(), writer, **limits)


@pytest.mark.asyncio
async def test_blocked_a_does_not_delay_b_and_each_preserves_order():
    """Las barreras comprueban orden/aislamiento sin depender de un benchmark."""
    first, second = peer(), peer()
    blocked, release, delivered = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow_drain():
        blocked.set()
        await release.wait()

    first.writer.drain.side_effect = slow_drain
    second.writer.drain.side_effect = delivered.set
    maps = MapManager()
    maps.add_player(1, 1, MessageSender(first), "Uno")
    maps.add_player(1, 2, MessageSender(second), "Dos")
    broadcast = MultiplayerBroadcastService(maps, MagicMock(), MagicMock())
    try:
        await broadcast.broadcast_character_remove(1, 10)
        await asyncio.wait_for(blocked.wait(), timeout=1)
        await asyncio.wait_for(delivered.wait(), timeout=1)
        assert not release.is_set()
        await broadcast.broadcast_character_remove(1, 11)
        await second.flush()
        assert second.writer.write.call_count == 2
        assert first.pending_packets == 2
        release.set()
        await first.flush()
        assert first.writer.write.call_args_list == second.writer.write.call_args_list
    finally:
        release.set()
        first.close()
        second.close()
        await first.wait_closed()
        await second.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("overflow", ["packets", "bytes"])
async def test_limits_include_inflight_data_and_cleanup_on_overflow(overflow):
    """Un drain bloqueado conserva su presupuesto hasta que el escritor termina."""
    connection = peer(
        max_outgoing_packets=2 if overflow == "packets" else 10,
        max_outgoing_bytes=16 if overflow == "packets" else 4,
    )
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked():
        entered.set()
        await release.wait()

    connection.writer.drain.side_effect = blocked
    try:
        await connection.send(b"aa")
        await entered.wait()
        await connection.send(b"b" if overflow == "packets" else b"bb")
        assert connection.pending_packets == 2
        assert connection.pending_bytes <= 4
        await connection.send(b"c")
        await connection.wait_closed()
        assert connection.pending_packets == 0
        assert connection.pending_bytes == 0
        assert connection._writer_task.done()
        connection.writer.transport.abort.assert_called_once()
        with pytest.raises(ConnectionError, match="salida pendiente"):
            await connection.flush()
    finally:
        release.set()
        connection.close()
        await connection.wait_closed()


@pytest.mark.asyncio
async def test_fast_burst_does_not_overflow_and_cancellation_leaves_no_writer():
    """Un escritor rápido consume mientras el productor cede cooperativamente."""
    connection = peer(max_outgoing_packets=2)
    try:
        for number in range(30):
            await connection.send(bytes([number]))
        await connection.flush()
        assert connection.writer.write.call_count == 30
        connection.writer.transport.abort.assert_not_called()
    finally:
        connection.close()
        connection.close()  # Cierre idempotente.
        await connection.wait_closed()
    assert connection.pending_packets == 0
    assert connection.pending_bytes == 0
    assert connection._writer_task.done()


@pytest.mark.asyncio
async def test_writer_error_discards_queue_and_does_not_leave_task(caplog):
    """Los errores se recogen y no se imprimen sus argumentos sensibles."""
    connection = peer()
    canary = "SyntheticQueueSecret116"
    connection.writer.drain.side_effect = RuntimeError(canary)
    try:
        await connection.send(b"data")
        await connection.wait_closed()
        assert connection.pending_packets == 0
        assert connection.pending_bytes == 0
        assert canary not in caplog.text
    finally:
        connection.close()
        await connection.wait_closed()
