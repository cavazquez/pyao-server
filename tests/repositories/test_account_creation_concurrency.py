"""Altas concurrentes y lectura deliberadamente obsoleta del contador compartido."""

import asyncio
from typing import Self
from unittest.mock import patch

import pytest

from src.repositories.account_repository import AccountRepository
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_twenty_parallel_signups_preserve_every_identity(redis_client):
    """Cada cuenta conserva perfil, índice, contraseña y estado fiscal independientes."""
    accounts = AccountRepository(redis_client)
    ids = await asyncio.gather(
        *(
            accounts.create_account(
                f"Concurrent{index}", f"synthetic-hash-{index}", "fixture@example.invalid"
            )
            for index in range(20)
        )
    )
    assert len(set(ids)) == 20
    for index, user_id in enumerate(ids):
        account = await accounts.get_account_by_user_id(user_id)
        assert account["username"] == f"Concurrent{index}"
        assert account["password_hash"] == f"synthetic-hash-{index}"
        assert await redis_client.hget(f"tax:{user_id}:state", "version") == "1"


@pytest.mark.asyncio
async def test_changed_counter_is_retried_before_claiming_corruption(redis_client):
    """Otra alta confirma exactamente entre leer el contador y consultar el índice."""
    accounts = AccountRepository(redis_client)
    original = redis_client.redis.pipeline
    paused, committed = asyncio.Event(), asyncio.Event()
    already_paused = False

    class InterleavedPipeline:
        def __init__(self, inner) -> None:
            self.inner = inner

        async def __aenter__(self) -> Self:
            await self.inner.__aenter__()
            return self

        async def __aexit__(self, *args: object) -> bool | None:
            return await self.inner.__aexit__(*args)

        def __getattr__(self, name: str) -> object:
            return getattr(self.inner, name)

        def get(self, key):
            result = self.inner.get(key)
            if self.inner.explicit_transaction:
                return result

            async def read():
                nonlocal already_paused
                value = await result
                if key == RedisKeys.ACCOUNTS_COUNTER and not already_paused:
                    already_paused = True
                    paused.set()
                    await asyncio.wait_for(committed.wait(), 3)
                return value

            return read()

    async def second_signup():
        await asyncio.wait_for(paused.wait(), 3)
        try:
            return await accounts.create_account(
                "Second", "synthetic-second", "fixture@example.invalid"
            )
        finally:
            committed.set()

    with patch.object(
        redis_client.redis,
        "pipeline",
        side_effect=lambda *a, **kw: InterleavedPipeline(original(*a, **kw)),
    ):
        first, second = await asyncio.gather(
            accounts.create_account("First", "synthetic-first", "fixture@example.invalid"),
            second_signup(),
        )
    assert (first, second) == (2, 1)
    assert (await accounts.get_account_by_user_id(first))["username"] == "First"
    assert (await accounts.get_account_by_user_id(second))["username"] == "Second"
