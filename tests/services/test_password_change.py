"""Cambio atómico, ACK perdido, propiedad de cuenta y ausencia de secretos en respuestas."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError

from src.repositories.account_repository import AccountRepository
from src.security.password_executor import get_password_executor
from src.services.password_change import (
    build_password_reply,
    change_password,
    password_change_status,
)
from src.utils.gold_atomic import operation_id
from src.utils.password_utils import hash_password
from src.utils.redis_config import RedisKeys

OLD = "Synthetic-Current-P127"
NEW = "Synthetic-Changed-P127"


@pytest_asyncio.fixture
async def profile(redis_client):
    """Crea únicamente una cuenta sintética y sustituye fsync en pruebas rápidas.

    Yields:
        Repositorio, usuario, nombre y hash inicial, sin imprimir credenciales.
    """
    account = AccountRepository(redis_client)
    username = "ClavePeña"
    encoded = await get_password_executor().run(hash_password, OLD)
    user_id = await account.create_account(username, encoded, "test@example.invalid")
    with patch("src.services.password_change.require_durable", new=AsyncMock()):
        yield account, user_id, username, encoded


@pytest.mark.asyncio
async def test_changed_password_logs_in_and_previous_does_not(profile, caplog):
    """El resultado público nunca incluye hashes, claves ni otro campo privado."""
    caplog.set_level(logging.DEBUG)
    repo, user, username, previous = profile
    before = await repo.get_account(username)
    identity = operation_id()
    result = await change_password(repo.redis.redis, username, user, identity, OLD, NEW)
    assert result == {"applied": True, "message": "Contraseña actualizada."}
    assert await repo.verify_password(username, NEW)
    assert not await repo.verify_password(username, OLD)
    after = await repo.get_account(username)
    assert after["password_hash"] != previous
    assert {key: value for key, value in after.items() if key != "password_hash"} == {
        key: value for key, value in before.items() if key != "password_hash"
    }
    status, message = await password_change_status(repo.redis.redis, username, user, identity)
    packet = build_password_reply(identity, status, message)
    for secret in (OLD, NEW, previous, after["password_hash"]):
        assert secret.encode("latin-1") not in packet
        assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current", "new"), [("incorrecta", NEW), (OLD, "corta"), (OLD, "x" * 33), (OLD, "nueva🙂")]
)
async def test_rejection_keeps_hash_and_has_queryable_result(profile, current, new):
    """Fallar credencial/política no sustituye ni elimina el hash existente."""
    repo, user, username, previous = profile
    identity = operation_id()
    assert not (await change_password(repo.redis.redis, username, user, identity, current, new))[
        "applied"
    ]
    assert (await repo.get_account(username))["password_hash"] == previous
    assert (await password_change_status(repo.redis.redis, username, user, identity))[0] == 2


@pytest.mark.asyncio
async def test_concurrent_replay_and_changed_payload_do_not_replace_again(profile):
    """Un ID repetido admite la misma operación y rechaza otra clave nueva."""
    repo, user, username, _previous = profile
    identity = operation_id()
    results = await asyncio.gather(
        *(change_password(repo.redis.redis, username, user, identity, OLD, NEW) for _ in range(2))
    )
    assert all(result["applied"] for result in results)
    saved = (await repo.get_account(username))["password_hash"]
    assert (await change_password(repo.redis.redis, username, user, identity, OLD, NEW))["applied"]
    assert not (
        await change_password(repo.redis.redis, username, user, identity, OLD, "Different-New-127")
    )["applied"]
    assert (await repo.get_account(username))["password_hash"] == saved


@pytest.mark.asyncio
@pytest.mark.parametrize("after_exec", [False, True])
async def test_lost_exec_ack_preserves_single_replacement(profile, after_exec):
    """La consulta y el retry usan el mismo recibo, sin reembolsar/restaurar hashes viejos."""
    repo, user, username, _previous = profile
    original = type(repo.redis.redis.pipeline()).execute
    failed = False

    async def fail_once(self, *args: object, **kwargs: object):
        nonlocal failed
        if not failed:
            failed = True
            if after_exec:
                await original(self, *args, **kwargs)
            message = "ACK de prueba perdido"
            raise RedisConnectionError(message)
        return await original(self, *args, **kwargs)

    identity = operation_id()
    with patch.object(type(repo.redis.redis.pipeline()), "execute", fail_once):
        assert (await change_password(repo.redis.redis, username, user, identity, OLD, NEW))[
            "applied"
        ]
    assert (await password_change_status(repo.redis.redis, username, user, identity))[0] == 1
    assert await repo.verify_password(username, NEW)
    assert not await repo.verify_password(username, OLD)


@pytest.mark.asyncio
async def test_foreign_user_cannot_replace_hash_or_read_receipt(profile):
    """La cuenta del snapshot y el fingerprint deben coincidir con la sesión."""
    repo, user, username, previous = profile
    identity = operation_id()
    assert not (await change_password(repo.redis.redis, username, user + 1, identity, OLD, NEW))[
        "applied"
    ]
    assert (await repo.get_account(username))["password_hash"] == previous
    with pytest.raises(ValueError, match="reutilizado"):
        await password_change_status(repo.redis.redis, username, user, identity)


@pytest.mark.asyncio
async def test_login_rechecks_hash_after_verification(profile):
    """Una verificación lenta de una clave vieja no autentica un hash ya sustituido."""
    repo, _user, username, _previous = profile
    replacement = await get_password_executor().run(hash_password, NEW)

    async def verify_then_change(*_args: object):
        await repo.redis.hset(RedisKeys.account_data(username), "password_hash", replacement)
        return True

    with patch(
        "src.repositories.account_repository.get_password_executor",
        return_value=SimpleNamespace(run=verify_then_change),
    ):
        assert not await repo.verify_password(username, OLD)


@pytest.mark.asyncio
async def test_absent_receipt_is_uncertain_not_a_false_failure(profile):
    """No se interpreta la ausencia de respuesta como una restauración de contraseña."""
    repo, user, username, _previous = profile
    assert (await password_change_status(repo.redis.redis, username, user, operation_id()))[0] == 3


@pytest.mark.asyncio
async def test_two_different_operations_only_replace_the_verified_hash_once(profile):
    """El segundo cambio no puede usar una verificación de la clave anterior ya invalidada."""
    repo, user, username, _previous = profile
    results = await asyncio.gather(
        *(
            change_password(repo.redis.redis, username, user, operation_id(), OLD, candidate)
            for candidate in (NEW, "Different-New-127")
        )
    )
    assert sum(result["applied"] for result in results) == 1
