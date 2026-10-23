"""Ensayo real de migración, carga, competencia, ACK perdido y recuperación AOF."""

import argparse

# ruff: noqa: S101 - invariantes de este ensayo descartable de aceptación.
import asyncio
import json
import math
import statistics
import time
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.items import ledger
from src.items.condition import condition
from src.items.ground_gc import BATCH_SIZE, QUEUE_KEY, RETIRED_TTL_SECONDS, collect
from src.items.migration import BOOTSTRAP_SOCKET_TIMEOUT, migrate
from src.items.policy import individual
from src.items.view import pages
from src.models.item_catalog import ItemCatalog
from src.models.skill_data_loader import SKILL_RULES_KEY
from src.operations.redis_sandbox import RedisSandbox
from src.runtime_paths import data_dir
from src.services.bank_item_transfer import transfer_bank_item
from src.services.combat.physical_plan import PhysicalPlan, PhysicalRequest, commit_physical
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.services.player.lifecycle import apply_player_damage, settle_death
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GROUND_TTL_SECONDS
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio.client import Pipeline


MAX_VIEW_BYTES = 3500
LATENCY_SAMPLES = 30


async def seed_fighters(redis: Redis) -> None:
    """Crea sólo actores sintéticos del ensayo, antes de migrar sus armas."""
    rules = tomllib.loads((data_dir() / "skills.toml").read_text())
    await redis.set(SKILL_RULES_KEY, json.dumps(rules))
    for user, x, y in ((2, 50, 50), (3, 51, 49)):
        await redis.hset(RedisKeys.player_inventory(user), mapping={"slot_1": "2:1"})
        await redis.hset(RedisKeys.player_equipment(user), mapping={"weapon": "1"})
        await redis.hset(
            RedisKeys.player_user_stats(user),
            mapping={
                "level": "40",
                "min_hp": "500",
                "max_hp": "500",
                "min_sta": "100",
                "max_sta": "100",
                "class_id": "3",
                "safe_mode": "0",
            },
        )
        await redis.hset(RedisKeys.player_stats(user), mapping={"strength": "20", "agility": "20"})
        await redis.hset(
            RedisKeys.player_position(user), mapping={"map": "2", "x": str(x), "y": str(y)}
        )
    await redis.hset(
        RedisKeys.npc_instance("items-battle"),
        mapping={
            "npc_id": "500",
            "instance_id": "items-battle",
            "map_id": "2",
            "x": "51",
            "y": "50",
            "hp": "1",
            "max_hp": "1",
            "is_attackable": "True",
            "level": "1",
        },
    )


async def battle_and_death(redis: Redis) -> dict[str, Any]:
    """Compite por el mismo blanco y liquida una muerte conservando el equipo gastado.

    Returns:
        Estados a contrastar después de reiniciar Redis y medidas de conservación.
    """
    users = (2, 3)
    identities = [
        InventorySlot.parse(await redis.hget(RedisKeys.player_inventory(u), "slot_1")).instance_ids[
            0
        ]
        for u in users
    ]
    with patch("src.services.combat.physical_plan.random.random", return_value=0.0):
        plans = [
            PhysicalPlan(PhysicalRequest(u, target_npc="items-battle"), ItemCatalog(), 30, 20)
            for u in users
        ]
    operations = [operation_id() for _ in users]
    results = await asyncio.gather(
        *(commit_physical(redis, p, op) for p, op in zip(plans, operations, strict=True))
    )
    assert sum(bool(r["applied"]) for r in results) == 1
    for iid, result, plan, op in zip(identities, results, plans, operations, strict=True):
        assert await redis.hget(ledger.PREFIX + iid, "uses_spent") == str(int(result["applied"]))
        assert await commit_physical(redis, plan, op) == result
    winner = next(i for i, r in enumerate(results) if r["applied"])
    user, iid = users[winner], identities[winner]
    before = await redis.hgetall(ledger.PREFIX + iid)
    assert (await apply_player_damage(redis, user, 1000, operation_id()))["player_died"]
    position = await redis.hgetall(RedisKeys.player_position(user))
    deaths = await asyncio.gather(
        *(settle_death(redis, user, 0, 2, int(position["x"]), int(position["y"])) for _ in range(2))
    )
    assert sum(bool(row["applied"]) for row in deaths) == 1
    after = await redis.hgetall(ledger.PREFIX + iid)
    assert after["location"].startswith("ground_items:2|")
    assert all(before[k] == after[k] for k in ("created_at", "expires_at", "uses_spent"))
    return {
        "attackers": 2,
        "accepted_attacks": 1,
        "accepted_death_settlements": 1,
        "saved_states": {i: await redis.hgetall(ledger.PREFIX + i) for i in identities},
    }


async def latency(redis: Redis, *, individual: bool) -> dict[str, float | int]:
    """Mide lectura de veinte slots, con la semántica correspondiente a cada formato.

    Returns:
        Muestras, mediana, percentil 95 y máximo medidos en milisegundos.
    """
    timings = []
    for _ in range(LATENCY_SAMPLES):
        start = time.perf_counter()
        if individual:
            await pages(redis, {"merchant": ("merchant:1:inventory", tuple(range(1, 21)))})
        else:
            await redis.hgetall("merchant:1:inventory")
        timings.append((time.perf_counter() - start) * 1000)
    timings.sort()
    return {
        "samples": len(timings),
        "median_ms": round(statistics.median(timings), 4),
        "p95_ms": round(timings[math.ceil(len(timings) * 0.95) - 1], 4),
        "max_ms": round(max(timings), 4),
    }


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
    await seed_fighters(redis)
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
        "battle_and_death": await battle_and_death(redis),
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
    baseline_memory = await redis.info("memory")
    baseline_aof = await redis.info("persistence")
    legacy_latency = await latency(redis, individual=False)
    cpu_before = await redis.info("cpu")
    client_cpu_start = time.process_time()
    start = time.perf_counter()
    containers = await migrate(redis)
    elapsed = time.perf_counter() - start
    client_cpu = time.process_time() - client_cpu_start
    cpu_after = await redis.info("cpu")
    await redis.execute_command("WAITAOF", 1, 0, 10000)
    persistence = await redis.info("persistence")
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
        "legacy_used_memory": baseline_memory["used_memory"],
        "legacy_aof_bytes": baseline_aof["aof_current_size"],
        "individual_aof_bytes": persistence["aof_current_size"],
        "migration_client_cpu_seconds": round(client_cpu, 4),
        "migration_redis_cpu_seconds": round(
            sum(cpu_after[k] - cpu_before[k] for k in ("used_cpu_sys", "used_cpu_user")), 4
        ),
        "legacy_stock_hash_latency": legacy_latency,
        "individual_condition_pages_latency": await latency(redis, individual=True),
        "restart_does_not_remigrate": True,
    }


async def catalog_migration(redis: Redis) -> dict[str, Any]:
    """Comprueba el stock inicial real, también con lotes de miles de ejemplares.

    Returns:
        Cantidades, conservación, época y tiempo del primer arranque completo.
    """
    await redis.flushdb()
    merchants = tomllib.loads((data_dir() / "npcs/merchants.toml").read_text())["merchant"]
    originals = {
        f"merchant:{index}:inventory": {
            f"slot_{slot}": f"{item['item_id']}:{item['quantity']}"
            for slot, item in enumerate(merchant["item"], 1)
        }
        for index, merchant in enumerate(merchants, 1)
    }
    async with redis.pipeline(transaction=False) as pipe:
        for key, original in originals.items():
            pipe.hset(key, mapping=original)
        await pipe.execute()
    start = time.perf_counter()
    count = await migrate(redis)
    elapsed = time.perf_counter() - start
    assert redis.connection_pool.connection_kwargs["socket_timeout"] == 5
    epoch = await redis.get("items:migration:epoch")
    expected_ids: set[str] = set()
    expected_units = 0
    for key, original in originals.items():
        assert json.loads(await redis.get("items:migration:backup:" + key)) == original
        migrated = await redis.hgetall(key)
        for field, raw in original.items():
            before, after = InventorySlot.parse(raw), InventorySlot.parse(migrated[field])
            assert before is not None and after is not None
            assert (before.item_id, before.quantity) == (after.item_id, after.quantity)
            if not individual(before.item_id):
                continue
            assert len(after.instance_ids) == before.quantity
            expected_units += before.quantity
            expected_ids.update(after.instance_ids)
            for iid in {
                after.instance_ids[0],
                after.instance_ids[len(after.instance_ids) // 2],
                after.instance_ids[-1],
            }:
                state = await redis.hgetall(ledger.PREFIX + iid)
                assert state["id"] == iid and state["item_id"] == str(before.item_id)
                assert state["location"] == key + "|" + field
                assert state["created_at"] == epoch and state["uses_spent"] == "0"
    actual = {
        key.removeprefix(ledger.PREFIX)
        async for key in redis.scan_iter(match=ledger.PREFIX + "*", count=5000)
    }
    assert actual == expected_ids and len(actual) == expected_units
    assert await migrate(redis) == 0
    return {
        "merchant_containers": count,
        "individual_objects": expected_units,
        "migration_seconds": round(elapsed, 3),
        "all_identities_present": True,
        "legacy_stock_preserved": True,
        "original_backups_preserved": True,
        "fixed_birth_epoch": True,
        "rerun_is_idempotent": True,
        "runtime_socket_timeout_seconds": 5,
        "bootstrap_socket_timeout_seconds": BOOTSTRAP_SOCKET_TIMEOUT,
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
            for iid, state in result["battle_and_death"].pop("saved_states").items():
                assert client.hgetall(ledger.PREFIX + iid) == state
            result["battle_and_death"]["aof_preserves_attacker_uses_and_death_drop"] = True
            options = client.connection_pool.connection_kwargs
            settings = {k: options[k] for k in ("host", "port", "password", "decode_responses")}

        async def benchmark() -> list[dict[str, Any]]:
            async with Redis(**settings) as redis:
                return [await load(redis, count) for count in (1000, 100000)]

        result["load"] = asyncio.run(benchmark())

        async def initial_stock() -> dict[str, Any]:
            async with Redis(**settings, socket_timeout=5, socket_connect_timeout=5) as redis:
                return await catalog_migration(redis)

        result["full_catalog_migration"] = asyncio.run(initial_stock())
        (args.output / "redis-items.json").write_text(json.dumps(result, indent=2) + "\n")
    print("ITEM_INSTANCES: PASS")


if __name__ == "__main__":
    main()
