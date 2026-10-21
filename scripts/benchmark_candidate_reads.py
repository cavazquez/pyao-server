"""Compare actual player repository candidate reads in disposable Redis.

python scripts/benchmark_candidate_reads.py --output artifacts/candidate-reads.json
No existing database endpoint is accepted. Counts exclude fixture setup.
"""

import argparse
import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
from typing import Any
from unittest.mock import patch

from redis.asyncio.client import Pipeline

from src.economy.tax_transactions import tax_key
from src.economy.taxes import utc_day
from src.operations.redis_sandbox import RedisSandbox
from src.repositories.player_repository import PlayerRepository
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys
from src.config.game_config import RedisConfig


async def run(sandbox: RedisSandbox) -> list[dict[str, object]]:
    client = RedisClient()
    await client.connect(
        RedisConfig(host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file),
        seed_defaults=False,
    )
    try:
        raw = client.redis
        repo = PlayerRepository(client)
        async with raw.pipeline(transaction=False) as pipe:
            for user in range(1, 501):
                pipe.hset(
                    RedisKeys.player_position(user),
                    mapping={"x": "50", "y": "50", "map": str((user - 1) % 50 + 1)},
                )
                pipe.hset(RedisKeys.player_user_stats(user), mapping={"min_hp": "100"})
                pipe.hset(tax_key(user), mapping={"last_day": str(utc_day())})
            await pipe.execute()
        counts: Counter[str] = Counter()
        execute_command: Callable[..., Awaitable[Any]] = raw.execute_command

        # Redis response callbacks deliberately expose dynamic values. Keep that
        # boundary typed while preserving the same wire-command instrumentation.
        async def counted_command(*args: Any, **kwargs: Any) -> Any:
            counts[str(args[0])] += 1
            return await execute_command(*args, **kwargs)

        class CountedPipeline(Pipeline):
            async def execute(self, raise_on_error: bool = True) -> list[Any]:
                counts.update(str(command[0][0]) for command in self.command_stack)
                return await super().execute(raise_on_error=raise_on_error)

        def counted_pipeline(transaction: bool = True, shard_hint: str | None = None) -> Pipeline:
            return CountedPipeline(
                raw.connection_pool, raw.response_callbacks, transaction, shard_hint
            )

        async def previous(ids: list[int]) -> dict[int, dict[str, int]]:
            result = {}
            for user in ids:
                if await repo.is_alive(user):
                    position = await repo.get_position(user)
                    if position:
                        result[user] = position
            return result

        async def measure(operation: Callable[[], Awaitable[object]]) -> dict[str, object]:
            counts.clear()
            await operation()
            per_call = dict(counts)
            values = []
            for _ in range(31):
                started = time.perf_counter_ns()
                await operation()
                values.append((time.perf_counter_ns() - started) / 1000)
            values.sort()
            return {
                "p50_us": statistics.median(values),
                "p95_us": values[29],
                "p99_us": values[30],
                "samples": 31,
                "commands_per_call": per_call,
            }

        results: list[dict[str, object]] = []
        with (
            patch.object(raw, "execute_command", counted_command),
            patch.object(raw, "pipeline", counted_pipeline),
        ):
            for count in (20, 50, 500):
                ids = list(range(1, count + 1))
                assert await previous(ids) == await repo.get_positions(ids, alive_only=True)
                results.append(
                    {
                        "candidate_players": count,
                        "previous": await measure(lambda: previous(ids)),
                        "batched": await measure(lambda: repo.get_positions(ids, alive_only=True)),
                        "batch_size": 256,
                        "snapshots_retained_between_calls": False,
                    }
                )
        return results
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with RedisSandbox() as sandbox:
        rows = asyncio.run(run(sandbox))
    root = Path(__file__).resolve().parents[1]
    report = {
        "python": platform.python_version(),
        "cases": rows,
        "source_hashes": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in (
                "src/repositories/player_mixins/_position_mixin.py",
                "src/services/npc/npc_ai_service.py",
                "src/effects/npc_ai_effect.py",
            )
        },
        "limitations": [
            "Already-settled daily balances, live candidates, loopback Redis",
            "Compares actual previous selection route and actual new batch method; no attack or transport",
            "500 candidates span two bounded pipelines; not 500 connected clients",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
