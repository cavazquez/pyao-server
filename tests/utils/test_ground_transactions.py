"""Alcance acotado del suelo, replay entre esquemas y publicación desde Redis."""

import json
from hashlib import sha256
from unittest.mock import AsyncMock, patch

import pytest

from src.game.ground_item_index import GroundItemIndex
from src.repositories.ground_items_repository import GroundItemsRepository
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GroundState, stack_identity
from src.utils.ground_storage import decode_fields, encode_fields, read_ground
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import (
    Decision,
    Resource,
    read_resource_receipt,
    transact,
)


def test_hash_field_must_contain_one_complete_json_list():
    """Un valor malformado no puede inyectar otras coordenadas en el snapshot."""
    with pytest.raises(json.JSONDecodeError):
        decode_fields(1, {"1,1": '[],"2,2":[]'})


@pytest.mark.asyncio
async def test_one_tile_mutation_and_cache_refresh_never_read_the_whole_map(redis_client):
    """5.000 casillas no amplían el alcance del append ni del refresco local."""
    redis = redis_client.redis
    key = RedisKeys.ground_items(1)
    state = GroundState(
        1,
        json.dumps(
            {
                f"{i % 100 + 1},{i // 100 + 1}": [
                    {"item_id": 1, "quantity": 1, "stack_id": stack_identity(str(i))}
                ]
                for i in range(5000)
            }
        ),
    )
    original = encode_fields(state)
    await redis.hset(key, mapping=original)
    repo = GroundItemsRepository(redis_client)
    index = GroundItemIndex(10, repo)
    await index.load_ground_items(1)
    untouched = index.get_ground_items(1, 1, 1)
    pipe_type = type(redis.pipeline())
    getall = pipe_type.hgetall
    hmget = pipe_type.hmget
    requests = []

    def prohibit_full_read(pipe, name):
        assert name != key, "Una acción puntual leyó todo el suelo"
        return getall(pipe, name)

    def scoped_read(pipe, name, fields, *args: object):
        if name == key:
            requests.append(tuple(fields))
        return hmget(pipe, name, fields, *args)

    with (
        patch("src.repositories.ground_items_repository.require_durable", new=AsyncMock()),
        patch.object(pipe_type, "hgetall", prohibit_full_read),
        patch.object(pipe_type, "hmget", scoped_read),
        patch.object(redis, "hgetall", side_effect=AssertionError("Refresco global")),
    ):
        assert await index.add_committed(1, 100, 100, {"item_id": 1, "quantity": 1}, None)
    assert requests
    assert all(fields == ("100,100",) for fields in requests)
    assert index.get_ground_items(1, 1, 1) is untouched
    current = await redis.hgetall(key)
    assert {field: value for field, value in current.items() if field != "100,100"} == original


@pytest.mark.asyncio
async def test_decision_cannot_write_a_tile_outside_its_declared_scope(redis_client):
    """Una decisión inválida no aplica saldos ni genera un recibo de éxito."""
    redis = redis_client.redis
    key = RedisKeys.ground_items(1)
    state = GroundState(1, None)
    state.append(2, 2, {"item_id": 1, "quantity": 1, "stack_id": stack_identity("outside")})
    identity = operation_id()
    with pytest.raises(ValueError, match="fuera de las casillas"):
        await transact(
            redis,
            (Resource(key, "ground", fields=("1,1",)),),
            identity,
            {"scope": 1},
            lambda _snapshot: Decision({"applied": True}, {key: state.encode()}),
        )
    assert not await redis.exists(key)
    assert not await redis.exists(f"operation:resources:{identity}")


@pytest.mark.asyncio
async def test_new_receipt_binds_the_scope_but_old_receipts_survive_migration(redis_client):
    """La compatibilidad se limita a recibos previos, nunca permite ampliar uno nuevo."""
    redis = redis_client.redis
    key = RedisKeys.ground_items(1)
    request = {"x": 1, "y": 1}
    identity = operation_id()
    result = {"applied": True, "quantity": 2}
    await redis.set(
        f"operation:resources:{identity}",
        json.dumps(
            {
                "request": sha256(
                    b'{"request":{"x":1,"y":1},"resources":[["ground_items:1","string"]]}'
                ).hexdigest(),
                "result": result,
            }
        ),
        ex=600,
    )
    resources = (Resource(key, "ground", fields=("1,1",)),)
    assert await read_resource_receipt(redis, resources, identity, request) == result
    assert (
        await transact(redis, resources, identity, request, lambda _s: pytest.fail("Reaplicado"))
        == result
    )
    new = operation_id()
    await transact(redis, resources, new, request, lambda _s: Decision(result, {}))
    with pytest.raises(ValueError, match="otra petición"):
        await transact(
            redis,
            (Resource(key, "ground", fields=("2,2",)),),
            new,
            request,
            lambda _s: pytest.fail("Alcance ampliado"),
        )


@pytest.mark.asyncio
async def test_expiry_between_watch_and_exec_cannot_credit_an_expired_stack(redis_client):
    """Vencer el mapa obliga a releer; no se acreditan objetos ya desaparecidos."""
    redis = redis_client.redis
    key = RedisKeys.ground_items(1)
    state = GroundState(1, None)
    identity = stack_identity("expiring")
    state.append(1, 1, {"item_id": 1, "quantity": 2, "stack_id": identity})
    await redis.hset(key, mapping=encode_fields(state))
    await redis.hset(RedisKeys.player_position(1), mapping={"map": "1", "x": "1", "y": "1"})
    await redis.hset(RedisKeys.player_user_stats(1), mapping={"gold": "50", "min_hp": "100"})
    pipeline_type = type(redis.pipeline())
    execute = pipeline_type.execute
    expired = False

    async def expire_before_exec(pipe, *args: object, **kwargs: object):
        nonlocal expired
        if not expired:
            expired = True
            await redis.pexpire(key, -1)
        return await execute(pipe, *args, **kwargs)

    with (
        patch("src.services.ground_transfer.require_durable", new=AsyncMock()),
        patch.object(pipeline_type, "execute", expire_before_exec),
    ):
        result = await transfer_ground(
            redis, GroundRequest(1, 1, 1, 1, "pickup", expected_stack=identity), operation_id()
        )
    assert not result["applied"]
    assert await redis.hget(RedisKeys.player_user_stats(1), "gold") == "50"
    assert not await redis.hgetall(RedisKeys.player_inventory(1))
    assert not (await read_ground(redis, 1)).positions()
