"""Compara drop/pickup y refresco local, con AOF, en un Redis descartable propio.

--baseline apunta a fuentes anteriores exportadas por Git. Los workers sólo
reciben el endpoint aleatorio creado por RedisSandbox en este proceso padre.
No acepta un Redis de producción ni construye distribuciones.
"""

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def percentiles(values):
    values = sorted(values)
    return {
        "p50_ms": statistics.median(values),
        "p95_ms": values[min(len(values) - 1, int(len(values) * 0.95))],
        "p99_ms": values[min(len(values) - 1, int(len(values) * 0.99))],
        "max_ms": max(values),
    }


async def worker(args):
    sys.path.insert(0, str(args.checkout))
    from redis.asyncio import Redis
    from redis.asyncio.client import Pipeline
    from src.config.game_config import RedisConfig
    from src.economy.tax_transactions import tax_key
    from src.economy.taxes import TAX_POLICY_KEY, utc_day
    from src.game.map_manager import MapManager
    from src.repositories.ground_items_repository import GroundItemsRepository
    from src.services.ground_transfer import GroundRequest, transfer_ground
    from src.utils.gold_atomic import operation_id
    from src.utils.ground_state import GroundState, stack_identity
    from src.utils.redis_client import RedisClient
    from src.utils.redis_config import RedisKeys

    client = RedisClient()
    await client.connect(
        RedisConfig(host="127.0.0.1", port=args.port, password_file=args.password_file),
        seed_defaults=False,
    )
    redis = client.redis
    key = RedisKeys.ground_items(1)
    metrics = {"read": 0, "write": 0}
    execute = Redis.execute_command
    pipe_execute = Pipeline.execute_command

    def selected(arguments):
        return len(arguments) > 1 and arguments[1] == key

    def payload(reply):
        if isinstance(reply, (list, tuple)):
            return sum(payload(value) for value in reply)
        if isinstance(reply, dict):
            return sum(payload(value) for value in reply.values())
        if reply is None:
            return 0
        return len(reply if isinstance(reply, bytes) else str(reply).encode())

    def record_write(arguments):
        if selected(arguments):
            command = str(arguments[0]).upper()
            if command == "SET":
                metrics["write"] += payload(arguments[2])
            elif command == "HSET":
                metrics["write"] += sum(payload(value) for value in arguments[3::2])

    async def tracked_execute(connection, *arguments, **kwargs):
        reply = await execute(connection, *arguments, **kwargs)
        if selected(arguments) and str(arguments[0]).upper() in {"GET", "HMGET", "HGETALL"}:
            metrics["read"] += payload(reply)
        record_write(arguments)
        return reply

    def tracked_pipeline(connection, *arguments, **kwargs):
        result = pipe_execute(connection, *arguments, **kwargs)
        record_write(arguments)
        if selected(arguments) and str(arguments[0]).upper() in {"GET", "HMGET", "HGETALL"}:

            async def read():
                reply = await result
                metrics["read"] += payload(reply)
                return reply

            return read()
        return result

    results = []
    try:
        for count in (100, 1000, 5000):
            await redis.delete(key)
            values = {
                f"{i % 100 + 1},{i // 100 + 1}": [
                    {"item_id": 15, "quantity": 1, "stack_id": stack_identity(f"fixture:{i}")}
                ]
                for i in range(count)
            }
            raw = json.dumps(values, separators=(",", ":"))
            if args.layout == "legacy":
                await redis.set(key, raw, ex=3600)
            else:
                await redis.hset(
                    key,
                    mapping={
                        field: json.dumps(items, separators=(",", ":"))
                        for field, items in values.items()
                    },
                )
                await redis.expire(key, 3600)
            today = utc_day()
            await redis.hset(
                TAX_POLICY_KEY,
                mapping={
                    "version": "1",
                    "enabled": "1",
                    "rate_bps": "100",
                    "activation_day": str(today),
                    "ground_activation_day": str(today),
                },
            )
            await redis.hset(
                tax_key(1),
                mapping={
                    "version": "1",
                    "last_day": str(today),
                    "remainder": "0",
                    "total_paid": "0",
                },
            )
            await redis.hset(
                RedisKeys.player_user_stats(1), mapping={"min_hp": "100", "gold": "1000"}
            )
            await redis.hset(
                RedisKeys.player_position(1), mapping={"map": "1", "x": "100", "y": "100"}
            )
            await redis.hset(RedisKeys.player_inventory(1), mapping={"slot_30": "15:20"})
            await redis.set(RedisKeys.bank_gold(1), "500")
            manager = MapManager(GroundItemsRepository(client))
            await manager.load_ground_items(1)
            memory = await redis.memory_usage(key)
            samples = {"drop": [], "pickup": []}
            sizes = {"drop": [], "pickup": []}
            with (
                patch.object(Redis, "execute_command", tracked_execute),
                patch.object(Pipeline, "execute_command", tracked_pipeline),
            ):
                for number in range(args.samples + 3):
                    for action in ("drop", "pickup"):
                        if action == "drop":
                            request = GroundRequest(
                                1,
                                1,
                                100,
                                100,
                                "drop_item",
                                slot=30,
                                quantity=1,
                                expected_item_id=15,
                            )
                        else:
                            request = GroundRequest(1, 1, 100, 100, "pickup", expected_stack=stack)
                        metrics.update(read=0, write=0)
                        identity = operation_id()
                        started = time.perf_counter_ns()
                        result = await manager.apply_ground_operation(
                            1,
                            100,
                            100,
                            redis,
                            lambda: transfer_ground(redis, request, identity),
                            operation_id=identity,
                        )
                        elapsed = (time.perf_counter_ns() - started) / 1_000_000
                        assert result["applied"], result
                        if action == "drop":
                            stack = result["item"]["stack_id"]
                        if number >= 3:
                            samples[action].append(elapsed)
                            sizes[action].append(dict(metrics))
            assert (await redis.hget(RedisKeys.player_inventory(1), "slot_30")) == "15:20"
            assert (await redis.hget(RedisKeys.player_user_stats(1), "gold")) == "1000"
            results.append(
                {
                    "positions": count,
                    "memory_usage_bytes": memory,
                    "legacy_json_bytes": len(raw.encode()),
                    **{
                        action: {
                            **percentiles(samples[action]),
                            "samples": len(samples[action]),
                            "ground_read_payload_bytes_p50": statistics.median(
                                row["read"] for row in sizes[action]
                            ),
                            "ground_write_payload_bytes_p50": statistics.median(
                                row["write"] for row in sizes[action]
                            ),
                        }
                        for action in samples
                    },
                }
            )
        evidence = {
            "layout": args.layout,
            "python": sys.version,
            "source_hashes": {
                name: hashlib.sha256((args.checkout / name).read_bytes()).hexdigest()
                for name in (
                    "src/utils/resource_transaction.py",
                    "src/game/ground_item_index.py",
                    "src/services/ground_transfer.py",
                    "src/utils/ground_state.py",
                    "src/utils/ground_storage.py",
                    "src/repositories/ground_items_repository.py",
                    "src/economy/ground_devaluation.py",
                    "src/economy/tax_transactions.py",
                    "src/utils/durability.py",
                )
                if (args.checkout / name).is_file()
            },
            "redis_version": (await redis.info("server"))["redis_version"],
            "appendfsync": (await redis.config_get("appendfsync"))["appendfsync"],
            "cases": results,
        }
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--samples", type=int, default=51)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--checkout", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--layout", choices=("legacy", "hash"), help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--password-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.samples < 20:
        parser.error("Se requieren al menos 20 muestras por operación")
    if args.worker:
        asyncio.run(worker(args))
        return
    sys.path.insert(0, str(ROOT))
    from src.operations.redis_sandbox import RedisSandbox

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "recorded_date": "2026-10-20",
        "production_data_used": False,
        "limitations": [
            "Synthetic positions, one sequential actor; not 5000 connected players",
            "Timings include authoritative transaction, AOF barriers and local cache refresh",
            "Payload bytes count ground JSON values, excluding RESP framing and other resources",
            "WATCH remains scoped to the whole map hash; unrelated writes may cause retries",
        ],
        "runs": {},
    }
    with RedisSandbox() as sandbox:
        args.output.with_suffix(".fixture.json").write_text(
            json.dumps({"container": sandbox.name, "volume": sandbox.volume}, indent=2) + "\n"
        )
        # La barrera AOF sigue activa. fsync always evita que la cadencia de un
        # segundo domine el microbenchmark de ambas implementaciones.
        with sandbox.client() as redis:
            redis.config_set("appendfsync", "always")
        for layout, checkout in (("legacy", args.baseline), ("hash", ROOT)):
            if checkout is None:
                continue
            destination = args.output.with_name(args.output.stem + "-" + layout + ".json")
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--checkout",
                    str(checkout.resolve()),
                    "--layout",
                    layout,
                    "--port",
                    str(sandbox.port),
                    "--password-file",
                    str(sandbox.password_file),
                    "--samples",
                    str(args.samples),
                    "--output",
                    str(destination),
                ],
                cwd=checkout,
                check=True,
                timeout=180,
            )
            result["runs"][layout] = json.loads(destination.read_text())
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                layout: [
                    {"positions": row["positions"], "drop": row["drop"], "pickup": row["pickup"]}
                    for row in run["cases"]
                ]
                for layout, run in result["runs"].items()
            }
        )
    )


if __name__ == "__main__":
    main()
