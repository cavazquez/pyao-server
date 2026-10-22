"""Borrado y reemplazo explícitos sin perder atomicidad ni recibos de recursos."""

import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.utils.gold_atomic import operation_id
from src.utils.resource_transaction import Decision, Resource, transact


@pytest.mark.asyncio
async def test_replacement_is_opt_in_and_deletes_only_declared_fields(redis_client):
    """Replacement is opt in and deletes only declared fields."""
    redis = redis_client.redis
    await redis.hset("test:hash", mapping={"old": "1", "keep": "2"})
    await redis.set("test:other", "untouched")
    await transact(
        redis,
        (Resource("test:hash", "hash"),),
        operation_id(),
        {},
        lambda _s: Decision({"applied": True}, {"test:hash": {"keep": "3"}}),
    )
    assert await redis.hgetall("test:hash") == {"old": "1", "keep": "3"}
    await transact(
        redis,
        (Resource("test:hash", "hash", replace=True),),
        operation_id(),
        {},
        lambda _s: Decision({"applied": True}, {"test:hash": {"new": "4"}}),
    )
    assert await redis.hgetall("test:hash") == {"new": "4"}
    assert await redis.get("test:other") == "untouched"


@pytest.mark.asyncio
async def test_lost_replacement_ack_and_delete_return_same_receipt(redis_client, monkeypatch):
    """Lost replacement ack and delete return same receipt."""
    redis, key = redis_client.redis, "test:members"
    await redis.hset(key, mapping={"removed": "1", "kept": "2"})
    await redis.set("test:user", "42")
    pipeline_type = type(redis.pipeline())
    original = pipeline_type.execute
    lost = False

    async def execute(pipe, *args: object, **kwargs: object):
        nonlocal lost
        result = await original(pipe, *args, **kwargs)
        if not lost:
            lost = True
            message = "synthetic lost EXEC ACK"
            raise RedisConnectionError(message)
        return result

    monkeypatch.setattr(pipeline_type, "execute", execute)
    identity = operation_id()
    resources = (
        Resource(key, "hash", replace=True),
        Resource("test:user", "string", deletable=True),
    )
    calls = 0

    def decide(_snapshot):
        nonlocal calls
        calls += 1
        return Decision({"applied": True}, {key: {"kept": "2"}, "test:user": None})

    first = await transact(redis, resources, identity, {"remove": 1}, decide)
    second = await transact(redis, resources, identity, {"remove": 1}, decide)
    assert first == second == {"applied": True}
    assert calls == 1
    assert await redis.hgetall(key) == {"kept": "2"}
    assert await redis.get("test:user") is None


@pytest.mark.asyncio
async def test_concurrent_hash_replacements_do_not_resurrect_removed_members(redis_client):
    """Concurrent hash replacements do not resurrect removed members."""
    redis, key = redis_client.redis, "test:members"
    await redis.hset(key, mapping={"A": "1", "B": "2", "C": "3"})

    async def remove(member):
        def decide(snapshot):
            remaining = dict(snapshot[key])
            remaining.pop(member, None)
            return Decision({"applied": True}, {key: remaining})

        return await transact(
            redis,
            (Resource(key, "hash", replace=True),),
            operation_id(),
            {"remove": member},
            decide,
        )

    assert all(result["applied"] for result in await asyncio.gather(remove("A"), remove("B")))
    assert await redis.hgetall(key) == {"C": "3"}


@pytest.mark.asyncio
async def test_invalid_write_never_deletes_hash_before_validation(redis_client):
    """Invalid write never deletes hash before validation."""
    redis, key = redis_client.redis, "test:hash"
    await redis.hset(key, "original", "1")
    with pytest.raises(ValueError, match="fuera de sus recursos o cambió su tipo"):
        await transact(
            redis,
            (Resource(key, "hash", replace=True),),
            operation_id(),
            {},
            lambda _s: Decision({"applied": True}, {key: "wrong type"}),
        )
    assert await redis.hgetall(key) == {"original": "1"}
    with pytest.raises(ValueError, match="eliminar un recurso no autorizado"):
        await transact(
            redis,
            (Resource(key, "hash"),),
            operation_id(),
            {},
            lambda _s: Decision({"applied": True}, {key: None}),
        )
    assert await redis.hgetall(key) == {"original": "1"}


@pytest.mark.asyncio
async def test_replacement_can_empty_hash_and_set_explicit_ttl(redis_client):
    """Replacement can empty hash and set explicit ttl."""
    redis, key = redis_client.redis, "test:hash"
    await redis.hset(key, "old", "1")
    await transact(
        redis,
        (Resource(key, "hash", replace=True, ttl_seconds=60),),
        operation_id(),
        {},
        lambda _s: Decision({"applied": True}, {key: {"fresh": "2"}}),
    )
    assert 0 < await redis.ttl(key) <= 60
    await transact(
        redis,
        (Resource(key, "hash", replace=True),),
        operation_id(),
        {},
        lambda _s: Decision({"applied": True}, {key: {}}),
    )
    assert await redis.hgetall(key) == {}
