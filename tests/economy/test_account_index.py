"""Índice directo de cuentas y adopción reanudable de identidades heredadas."""

import asyncio
from unittest.mock import patch

import pytest

from src.repositories.account_repository import USER_ACCOUNT_INDEX, AccountRepository
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_new_account_lookup_never_scans(redis_client):
    """Una cuenta nueva se resuelve por ID sin inspeccionar otras identidades."""
    repo = AccountRepository(redis_client)
    user = await repo.create_account("indexed", "synthetic-test-hash", "test@example.invalid")
    with patch.object(redis_client, "keys", side_effect=AssertionError("KEYS prohibido")):
        account = await repo.get_account_by_user_id(user)
    assert account["username"] == "indexed"
    assert not await repo.is_gm_by_user_id(user)


@pytest.mark.asyncio
async def test_legacy_backfill_is_repeatable_and_keeps_identity(redis_client):
    """La adopción por SCAN conserva datos y resuelve la misma cuenta."""
    await redis_client.hset(
        RedisKeys.account_data("legacy"),
        mapping={"username": "legacy", "user_id": "42", "is_gm": "1"},
    )
    await redis_client.set(RedisKeys.account_id_by_username("legacy"), "42")
    repo = AccountRepository(redis_client)
    await repo.backfill_user_index(batch_size=1)
    await repo.backfill_user_index(batch_size=1)
    assert await repo.is_gm_by_user_id(42)
    assert (await repo.get_account_by_user_id(42))["username"] == "legacy"


@pytest.mark.asyncio
async def test_conflicting_index_is_never_overwritten(redis_client):
    """Una identidad conflictiva detiene el backfill y no concede permisos GM."""
    await redis_client.hset(
        RedisKeys.account_data("legacy"),
        mapping={"username": "legacy", "user_id": "42", "is_gm": "1"},
    )
    await redis_client.set(RedisKeys.account_id_by_username("legacy"), "42")
    await redis_client.hset(USER_ACCOUNT_INDEX, "42", "other")
    repo = AccountRepository(redis_client)
    with pytest.raises(ValueError, match="mismo user_id"):
        await repo.backfill_user_index()
    assert await redis_client.hget(USER_ACCOUNT_INDEX, "42") == "other"
    assert await repo.get_account_by_user_id(42) is None


@pytest.mark.asyncio
async def test_racing_account_creations_do_not_duplicate_identity(redis_client):
    """Dos altas del mismo nombre confirman un único propietario e índice."""
    repo = AccountRepository(redis_client)
    results = await asyncio.gather(
        *(repo.create_account("racing", "test-hash", "test@example.invalid") for _ in range(2)),
        return_exceptions=True,
    )
    assert sum(type(result) is int for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    assert await redis_client.get(RedisKeys.ACCOUNTS_COUNTER) == "1"
    assert (await repo.get_account_by_user_id(1))["username"] == "racing"


@pytest.mark.asyncio
async def test_corrupt_counter_cannot_create_an_alias_to_a_gm(redis_client):
    """Un contador viejo no escribe un perfil que herede el ID de un GM."""
    repo = AccountRepository(redis_client)
    admin = await repo.create_account("admin", "test-hash", "test@example.invalid")
    await repo.set_gm_status("admin", True)
    await redis_client.set(RedisKeys.ACCOUNTS_COUNTER, "0")
    with pytest.raises(ValueError, match="reutilizar una identidad"):
        await repo.create_account("intruder", "other-hash", "test@example.invalid")
    assert await repo.get_account("intruder") is None
    assert await redis_client.get(RedisKeys.account_id_by_username("intruder")) is None
    assert await repo.is_gm_by_user_id(admin)
