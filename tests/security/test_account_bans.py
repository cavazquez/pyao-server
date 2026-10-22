"""Moderación autorizada y bloqueo de login/sesión con auditoría durable."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.network.client_connection import ClientConnection
from src.repositories.account_repository import AccountRepository
from src.security.account_bans import ban_key, is_blocked
from src.security.session_lease import SessionLease
from src.services.account_moderation import AccountModeration
from src.services.player.authentication_service import AuthenticationService
from src.utils.gold_atomic import operation_id


async def accounts(redis_client):
    """Crea dos identidades sintéticas y autoriza sólo al operador."""
    repo = AccountRepository(redis_client)
    actor = await repo.create_account("Operator", "synthetic-hash", "test@example.invalid")
    target = await repo.create_account("Target", "synthetic-hash", "test@example.invalid")
    await repo.set_gm_status("Operator", True)
    return repo, actor, target


@pytest.mark.parametrize(
    ("fields", "now", "expected"),
    [
        ({}, 100, False),
        ({"active": "0"}, 100, False),
        ({"active": "1", "expires": "0"}, 100, True),
        ({"active": "1", "expires": "101"}, 100, True),
        ({"active": "1", "expires": "100"}, 100, False),
    ],
)
def test_expiration_uses_server_time(fields, now, expected):
    """Un bloqueo temporal vence sin un proceso de limpieza ni reseteos de sesión."""
    assert is_blocked(fields, now=now) is expected


@pytest.mark.asyncio
async def test_regular_account_cannot_block_or_unblock(redis_client):
    """Una cuenta común no crea bloqueos, auditorías ni modifica privilegios."""
    repo, actor, target = await accounts(redis_client)
    service = AccountModeration(repo)
    for active in (True, False):
        result = await service.apply(target, "Operator", active=active, days=1, reason="test")
        assert not result["applied"]
    assert not await redis_client.redis.exists(ban_key(actor))
    assert await repo.is_gm_by_user_id(actor)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text", ["/BAN", "/BAN Operator invalid private", "/UNBAN", "/MUTE", "/UNMUTE"]
)
async def test_text_moderation_rejects_role_before_parsing_or_reading_target(redis_client, text):
    """Una petición incompleta tampoco salta la autorización ni consulta al objetivo."""
    repo, _actor, target = await accounts(redis_client)
    with patch.object(repo, "get_account", new=AsyncMock(wraps=repo.get_account)) as lookup:
        result = await AccountModeration(repo).handle_text(target, text)
        assert result == {"applied": False, "message": "No tienes permisos de moderación."}
        lookup.assert_awaited_once_with("Target")


@pytest.mark.asyncio
async def test_identified_ban_replays_one_audit_and_blocks_reservation(redis_client):
    """El replay no prolonga el bloqueo ni genera una segunda acción auditada."""
    repo, actor, target = await accounts(redis_client)
    service = AccountModeration(repo)
    identity = operation_id()
    with patch("src.services.account_moderation.require_durable", new=AsyncMock()):
        first = await service.apply(
            actor, "Target", active=True, days=1, reason="Ensayo sintético", identity=identity
        )
        again = await service.apply(
            actor, "Target", active=True, days=1, reason="Ensayo sintético", identity=identity
        )
    assert first == again
    assert first["applied"]
    assert not await SessionLease(redis_client.redis, target).acquire()
    assert is_blocked(await repo.get_account("Target"), prefix="ban_")
    audit = [key async for key in redis_client.redis.scan_iter(match="moderation:audit:*")]
    assert len(audit) == 1
    assert "password" not in await redis_client.redis.get(audit[0])


@pytest.mark.asyncio
async def test_ban_revokes_current_connection_before_returning(redis_client):
    """Una sesión ya publicada pierde su token y se cierra en esta instancia."""
    repo, actor, target = await accounts(redis_client)
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    peer = ClientConnection(MagicMock(), writer)
    peer.session_redis = redis_client.redis
    assert await peer.reserve_session(target)
    peer.mark_authenticated()
    try:
        with patch("src.services.account_moderation.require_durable", new=AsyncMock()):
            result = await AccountModeration(repo).apply(
                actor, "Target", active=True, days=0, reason="Ensayo sintético"
            )
        assert result["applied"]
        assert result["expires"] == 0
        assert not peer.is_authenticated
        writer.transport.abort.assert_called_once()
    finally:
        await peer.release_session()
        peer.close()
        await peer.wait_closed()


@pytest.mark.asyncio
async def test_unban_and_expiry_keep_audit_and_allow_new_login(redis_client):
    """Revocar o vencer conserva la auditoría y no hereda el token anterior."""
    repo, actor, target = await accounts(redis_client)
    service = AccountModeration(repo)
    with patch("src.services.account_moderation.require_durable", new=AsyncMock()):
        await service.apply(actor, "Target", active=True, days=1, reason="Ensayo temporal")
        result = await service.apply(
            actor, "Target", active=False, days=0, reason="Revocado por operador"
        )
    assert result["applied"]
    assert not is_blocked(await repo.get_account("Target"), prefix="ban_")
    await redis_client.redis.expire(f"session:{target}:owner", 0)
    lease = SessionLease(redis_client.redis, target)
    assert await lease.acquire()
    await lease.release()
    await redis_client.redis.hset(
        ban_key(target), mapping={"active": "1", "expires": str(int(time.time()) - 1)}
    )
    assert await lease.acquire()
    await lease.release()
    assert len([key async for key in redis_client.redis.scan_iter(match="moderation:audit:*")]) == 2


@pytest.mark.asyncio
async def test_authentication_checks_password_before_disclosing_account_ban(redis_client):
    """Una contraseña incorrecta conserva el error genérico incluso en una cuenta bloqueada."""
    repo, actor, target = await accounts(redis_client)
    sender = MagicMock()
    sender.connection.address = ("127.0.0.1", 12345)
    sender.send_error_msg = AsyncMock()
    with patch("src.services.account_moderation.require_durable", new=AsyncMock()):
        await AccountModeration(repo).apply(actor, "Target", active=True, days=0, reason="Ensayo")
    service = AuthenticationService(repo, sender)
    with patch.object(repo, "verify_password", new=AsyncMock(side_effect=[False, True])) as verify:
        assert await service.authenticate("Target", "synthetic-only") is None
        sender.send_error_msg.assert_awaited_with("Usuario o contraseña incorrectos")
        assert await service.authenticate("Target", "synthetic-only") is None
        assert "bloqueada" in sender.send_error_msg.call_args.args[0]
        assert verify.await_count == 2
    assert not await SessionLease(redis_client.redis, target).acquire()
