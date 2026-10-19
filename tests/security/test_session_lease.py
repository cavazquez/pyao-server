"""Reservas concurrentes y limpieza con el token de cada conexión."""

import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis.aioredis import FakeRedis

from src.command_handlers.login_handler import LoginCommandHandler
from src.commands.login_command import LoginCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.security.session_lease import SessionLease
from src.server import ArgentumServer
from src.tasks.player.task_login import TaskLogin


def connection(raw):
    """Construye una conexión real con un transporte sintético."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 1234)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    result = ClientConnection(MagicMock(), writer)
    result.session_redis = raw
    return result


def login_handler(sender, session):
    """Mantiene el handler real y reemplaza sólo los servicios de inicialización."""
    handler = LoginCommandHandler(
        MagicMock(), MagicMock(), None, None, None, None, None, None, sender, session
    )
    handler.player_repo.redis.hset = AsyncMock()
    handler.player_repo.is_sailing = AsyncMock(return_value=False)
    handler.auth_handler.authenticate_user = AsyncMock(return_value=(41, 1))
    position = {"map": 1, "x": 50, "y": 50, "heading": 3}
    handler.init_handler.send_login_packets = AsyncMock(return_value=position)
    handler.init_handler.initialize_player_data = AsyncMock()
    handler.init_handler.send_spellbook = AsyncMock()
    handler.spawn_handler.find_free_spawn_position = lambda current: current
    handler.spawn_handler.spawn_player = AsyncMock()
    handler.spawn_handler.send_map_data = AsyncMock()
    handler.finalization_handler.finalize_login = AsyncMock()
    return handler


@pytest.mark.asyncio
async def test_two_logins_publish_only_one_session():
    """Ambos pasan autenticación pero sólo el propietario llega al spawn."""
    raw = FakeRedis(decode_responses=True)
    first, second = connection(raw), connection(raw)
    sessions = [{}, {}]
    handlers = [
        login_handler(MessageSender(peer), session)
        for peer, session in zip([first, second], sessions, strict=True)
    ]
    entered = 0
    release = asyncio.Event()

    async def authenticate(_username, _password):
        nonlocal entered
        entered += 1
        if entered == 2:
            release.set()
        await release.wait()
        return 41, 1

    for handler in handlers:
        handler.auth_handler.authenticate_user = AsyncMock(side_effect=authenticate)
    try:
        canary = "Synthetic128"
        results = await asyncio.gather(
            *(h.handle(LoginCommand(username="Prueba", password=canary)) for h in handlers)
        )
        assert sum(result.success for result in results) == 1
        assert sum("user_id" in session for session in sessions) == 1
        assert sum(h.spawn_handler.spawn_player.await_count for h in handlers) == 1
        assert 0 < await raw.ttl("session:41:owner") <= 90
    finally:
        await first.release_session()
        await second.release_session()
        first.close()
        second.close()
        await first.wait_closed()
        await second.wait_closed()
        await raw.aclose()


@pytest.mark.asyncio
async def test_expired_owner_cannot_renew_or_release_new_session():
    """Una caída recupera por TTL y la liberación tardía no afecta otro token."""
    raw = FakeRedis(decode_responses=True)
    old, new = SessionLease(raw, 41), SessionLease(raw, 41)
    try:
        assert await old.acquire()
        assert not await new.acquire()
        await raw.expire(old.key, 0)  # Simular la expiración del lease tras la caída.
        assert await new.acquire()
        assert not await old.renew()
        assert not await old.release()
        assert await raw.get(new.key) == new.token
        assert await new.release()
        assert await new.release() is False
    finally:
        await raw.aclose()


@pytest.mark.asyncio
async def test_initialization_failure_releases_reservation():
    """Un error entre reservar y spawnear pasa por el finally del servidor."""
    raw = FakeRedis(decode_responses=True)
    server = ArgentumServer()
    deps = MagicMock()
    deps.redis_client.redis = raw
    deps.redis_client.increment_connections = AsyncMock()
    deps.redis_client.decrement_connections = AsyncMock()
    server.deps = deps
    peer = connection(raw)

    def field(value):
        return struct.pack("<H", len(value)) + value

    packet = b"\x00" + field(b"Prueba") + field(b"Synthetic128")
    reader = MagicMock(read=AsyncMock(side_effect=[packet, b""]))

    def task(data, sender, session):
        handler = login_handler(sender, session)
        handler.init_handler.send_login_packets.side_effect = RuntimeError("Fallo sintético")
        return TaskLogin(data, sender, handler, session)

    try:
        with patch.object(server, "create_task", side_effect=task):
            await server.handle_client(reader, peer.writer)
        assert await raw.get("session:41:owner") is None
        assert server._active_connections == 0
        retry = SessionLease(raw, 41)
        assert await retry.acquire()
        await retry.release()
    finally:
        await raw.aclose()


@pytest.mark.asyncio
async def test_cancelling_set_in_flight_releases_only_its_reservation():
    """Una cancelación espera el resultado ambiguo del SET antes de retirar su token."""
    raw = FakeRedis(decode_responses=True)
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed_set(*args: object, **kwargs: object):
        entered.set()
        await release.wait()
        return await raw.set(*args, **kwargs)

    store = MagicMock()
    store.set = AsyncMock(side_effect=delayed_set)
    store.pipeline = raw.pipeline
    lease = SessionLease(store, 41)
    task = asyncio.create_task(lease.acquire())
    try:
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await raw.get(lease.key) is None
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await raw.aclose()
