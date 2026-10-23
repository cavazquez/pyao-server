"""Ensayo real de migración, carga, competencia, ACK perdido y recuperación AOF."""

import argparse

# ruff: noqa: S101 - invariantes de este ensayo descartable de aceptación.
import asyncio
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.items import ledger
from src.items.condition import condition
from src.items.ground_gc import BATCH_SIZE, QUEUE_KEY, RETIRED_TTL_SECONDS, collect
from src.items.migration import migrate
from src.items.view import pages
from src.operations.redis_sandbox import RedisSandbox
from src.services.bank_item_transfer import transfer_bank_item
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GROUND_TTL_SECONDS
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio.client import Pipeline


MAX_VIEW_BYTES = 3500


async def ground_cleanup(redis: Redis, iid: str) -> dict[str, Any]:
    """Comprueba referencias reales, vencimiento del suelo y el límite de trabajo.

    Returns:
        Evidencia del retiro y de la conservación de objetos recuperados.
    """
    await redis.hset(RedisKeys.player_position(1), mapping={"map": "1", "x": "50", "y": "50"})
    result = await transfer_bank_item(redis, 1, 1, 1, "withdraw", operation_id())
    assert result["applied"]
    drop = GroundRequest(1, 1, 50, 50, "drop_item", slot=1, quantity=1, expected_item_id=2)
    result = await transfer_ground(redis, drop, operation_id())
    assert result["applied"]
    due = int(await redis.zscore(QUEUE_KEY, iid))
    assert await collect(redis, now=due) == (1, 0)
    assert await redis.hget(ledger.PREFIX + iid, "location") != "retired"
    ground_key = RedisKeys.ground_items(1)
    original_tile = await redis.hget(ground_key, "50,50")
    await redis.hset(ground_key, "50,50", "{invalid")
    assert await collect(redis, now=due + GROUND_TTL_SECONDS) == (1, 0)
    assert await redis.hget(ledger.PREFIX + iid, "location") != "retired"
    await redis.hset(ground_key, "50,50", original_tile)
    pickup = GroundRequest(1, 1, 50, 50, "pickup", expected_stack=result["item"]["stack_id"])
    assert (await transfer_ground(redis, pickup, operation_id()))["applied"]
    assert await redis.zscore(QUEUE_KEY, iid) is None
    # Una entrada derivada obsoleta tampoco puede retirar el objeto recogido.
    await redis.zadd(QUEUE_KEY, {iid: due})
    assert await collect(redis, now=due) == (1, 0)
    assert await redis.hget(ledger.PREFIX + iid, "location") != "retired"
    assert (await transfer_ground(redis, drop, operation_id()))["applied"]
    await redis.delete(RedisKeys.ground_items(1))
    assert await collect(redis, now=due + GROUND_TTL_SECONDS) == (1, 1)
    assert await redis.hget(ledger.PREFIX + iid, "location") == "retired"
    assert 0 < await redis.ttl(ledger.PREFIX + iid) <= RETIRED_TTL_SECONDS
    async with redis.pipeline() as pipe:
        for index in range(BATCH_SIZE + 1):
            fixture = f"{index + 10000:032x}"
            pipe.hset(
                ledger.PREFIX + fixture,
                mapping=ledger.new_state(fixture, 2, "ground_items:2|1,1/g1.fixture", due),
            )
            pipe.zadd(QUEUE_KEY, {fixture: due})
        await pipe.execute()
    assert await collect(redis, now=due) == (BATCH_SIZE, BATCH_SIZE)
    assert await collect(redis, now=due) == (1, 1)
    return {
        "keeps_live_references": True,
        "keeps_picked_up": True,
        "invalid_ground_does_not_delete": True,
        "batch_limit": BATCH_SIZE,
    }


async def exercise(redis: Redis) -> dict[str, Any]:
    """Manipula exclusivamente la base descartable creada por este ensayo.

    Returns:
        Medidas y comprobaciones independientes del resultado de las transacciones.
    """
    key, bank = RedisKeys.player_inventory(1), RedisKeys.bank(1)
    await redis.hset(key, mapping={"slot_1": "2:2"})
    await migrate(redis)
    iid = InventorySlot.parse(await redis.hget(key, "slot_1")).instance_ids[0]
    original = await redis.hgetall(ledger.PREFIX + iid)
    operation = operation_id()
    pipeline_type = type(redis.pipeline())
    execute = pipeline_type.execute
    lost = False

    async def lose_ack(pipe: Pipeline, *args: object, **kwargs: object) -> object:
        nonlocal lost
        result = await execute(pipe, *args, **kwargs)
        if not lost:
            lost = True
            message = "ACK perdido después del EXEC real"
            raise RedisConnectionError(message)
        return result

    with patch.object(pipeline_type, "execute", lose_ack):
        result = await transfer_bank_item(redis, 1, 1, 1, "deposit", operation)
        assert result["applied"]
        assert await transfer_bank_item(redis, 1, 1, 1, "deposit", operation) == result
    assert InventorySlot.parse(await redis.hget(bank, "slot_1")).instance_ids == (iid,)
    assert (await redis.hgetall(ledger.PREFIX + iid))["created_at"] == original["created_at"]
    contenders = await asyncio.gather(
        *(transfer_bank_item(redis, 1, 2, 1, "deposit", operation_id()) for _ in range(12))
    )
    assert sum(bool(row["applied"]) for row in contenders) == 1
    wear_id = operation_id()

    def decision(_snapshot: Snapshot) -> Decision:
        return Decision({"applied": True, "_item_uses": {iid: 1}}, {})

    result = await transact(redis, (Resource(bank, "hash"),), wear_id, {}, decision)
    assert await transact(redis, (Resource(bank, "hash"),), wear_id, {}, decision) == result
    assert await redis.hget(ledger.PREFIX + iid, "uses_spent") == "1"
    view = await pages(redis, {"bank": (bank, tuple(range(1, 41)))})
    assert all(len(json.dumps(row)) < MAX_VIEW_BYTES for row in view)
    state = await redis.hgetall(ledger.PREFIX + iid)
    state.update(uses_spent=state["max_uses"])
    assert condition(state, int(time.time())) == (0, 0, True)
    cleanup = await ground_cleanup(redis, iid)
    return {
        "ack_loss": True,
        "concurrent_deposits": len(contenders),
        "accepted_deposits": 1,
        "repeat_does_not_spend_uses": True,
        "bounded_pages": True,
        "ground_cleanup": cleanup,
        "recovery_iid": iid,
        "saved_state": await redis.hgetall(ledger.PREFIX + iid),
    }


async def load(redis: Redis, count: int) -> dict[str, Any]:
    """Mide objetos reales en Redis sin poblar jugadores ni cuentas productivas.

    Returns:
        Tiempo, memoria y cantidad de identidades después de una migración reiniciada.
    """
    await redis.flushdb()
    async with redis.pipeline(transaction=False) as pipe:
        for index in range(count // 20):
            pipe.hset(
                f"merchant:{index + 1}:inventory",
                mapping={f"slot_{s}": "2:1" for s in range(1, 21)},
            )
        await pipe.execute()
    start = time.perf_counter()
    containers = await migrate(redis)
    elapsed = time.perf_counter() - start
    assert await migrate(redis) == 0
    ids = [key async for key in redis.scan_iter(match=ledger.PREFIX + "*", count=1000)]
    assert len(ids) == count
    memory = await redis.info("memory")
    return {
        "objects": count,
        "containers": containers,
        "migration_seconds": round(elapsed, 3),
        "objects_per_second": round(count / elapsed),
        "used_memory": memory["used_memory"],
        "restart_does_not_remigrate": True,
    }


def main() -> None:
    """Crea y destruye sus propios contenedor, volumen y credenciales."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with RedisSandbox(purpose="recovery") as sandbox:
        with sandbox.client() as client:
            options = client.connection_pool.connection_kwargs
            settings = {k: options[k] for k in ("host", "port", "password", "decode_responses")}

        async def run() -> dict[str, Any]:
            async with Redis(**settings) as redis:
                result = await exercise(redis)
                await redis.execute_command("WAITAOF", 1, 0, 10000)
                return result

        result = asyncio.run(run())
        sandbox.recreate(appendonly=True)
        with sandbox.client() as client:
            assert client.hgetall(ledger.PREFIX + result["recovery_iid"]) == result.pop(
                "saved_state"
            )
            result["aof_restart_preserves_identity_and_uses"] = True
            options = client.connection_pool.connection_kwargs
            settings = {k: options[k] for k in ("host", "port", "password", "decode_responses")}

        async def benchmark() -> list[dict[str, Any]]:
            async with Redis(**settings) as redis:
                return [await load(redis, count) for count in (1000, 100000)]

        result["load"] = asyncio.run(benchmark())
        (args.output / "redis-items.json").write_text(json.dumps(result, indent=2) + "\n")
    print("ITEM_INSTANCES: PASS")


if __name__ == "__main__":
    main()
