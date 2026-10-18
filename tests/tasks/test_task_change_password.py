"""Frontera autenticada y presupuesto previo al hashing de contraseñas."""

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.game_config import SecurityConfig
from src.messaging.message_sender import MessageSender
from src.network.capabilities import Capability
from src.network.client_connection import ClientConnection
from src.repositories.account_repository import AccountRepository
from src.security.auth_limits import AuthLimiter
from src.tasks.task_change_password import TaskChangePassword
from src.utils.gold_atomic import operation_id


def packet(identity, current="Synthetic-Current", new="Synthetic-New"):
    """Construye una petición sin registrar su contenido."""
    return bytes([107, 1]) + b"".join(
        struct.pack("<H", len(value)) + value.encode("ascii") for value in (identity, current, new)
    )


def connection(authenticated=True, capabilities=8):
    """Usa la conexión real con un transporte que registra sólo para assertions."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 1234)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    peer = ClientConnection(MagicMock(), writer)
    if authenticated:
        peer.mark_authenticated()
    peer.capabilities.enabled = Capability(capabilities)
    return peer


@pytest.mark.asyncio
@pytest.mark.parametrize(("authenticated", "capabilities"), [(False, 8), (True, 0)])
async def test_missing_authentication_or_capability_never_calls_service(
    redis_client, authenticated, capabilities
):
    """Ni estado de sesión sobrante ni un ID válido habilitan hashing sin autorización."""
    peer = connection(authenticated, capabilities)
    try:
        with patch("src.tasks.task_change_password.change_password", new=AsyncMock()) as service:
            await TaskChangePassword(
                packet(operation_id()),
                MessageSender(peer),
                AccountRepository(redis_client),
                {"user_id": 1, "username": "BoundUser"},
            ).execute()
            service.assert_not_awaited()
        assert peer.pending_packets == 0
    finally:
        peer.close()
        await peer.wait_closed()


@pytest.mark.asyncio
async def test_rate_limit_rejects_before_password_service(redis_client):
    """Comparte el presupuesto de conexión/IP/cuenta utilizado en login."""
    peer = connection()
    config = SecurityConfig(auth_attempts_per_connection=1)
    peer.auth_limiter = AuthLimiter(config, clock=lambda: 100.0)
    peer.auth_attempts.window = int(100.0 // config.auth_window_seconds)
    peer.auth_attempts.count = 1
    try:
        with patch("src.tasks.task_change_password.change_password", new=AsyncMock()) as service:
            await TaskChangePassword(
                packet(operation_id()),
                MessageSender(peer),
                AccountRepository(redis_client),
                {"user_id": 1, "username": "BoundUser"},
            ).execute()
            service.assert_not_awaited()
        await peer.flush()
        output = b"".join(call.args[0] for call in peer.writer.write.call_args_list)
        assert output[0] == 253
        assert b"Synthetic-Current" not in output
        assert b"Synthetic-New" not in output
    finally:
        peer.close()
        await peer.wait_closed()


@pytest.mark.asyncio
async def test_status_query_never_reuses_or_hashes_credentials(redis_client):
    """La recuperación de un ack perdido es una consulta de la cuenta ya autenticada."""
    peer = connection()
    identity = operation_id()
    try:
        with (
            patch(
                "src.tasks.task_change_password.password_change_status",
                new=AsyncMock(return_value=(1, "Confirmado")),
            ) as status,
            patch("src.tasks.task_change_password.change_password", new=AsyncMock()) as change,
        ):
            await TaskChangePassword(
                packet(identity, "", ""),
                MessageSender(peer),
                AccountRepository(redis_client),
                {"user_id": 1, "username": "BoundUser"},
            ).execute()
            status.assert_awaited_once_with(redis_client.redis, "BoundUser", 1, identity)
            change.assert_not_awaited()
    finally:
        peer.close()
        await peer.wait_closed()
