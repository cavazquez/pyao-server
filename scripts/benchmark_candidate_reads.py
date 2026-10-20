"""Compare actual player repository candidate reads in disposable Redis.

python scripts/benchmark_candidate_reads.py --output artifacts/candidate-reads.json
No existing database endpoint is accepted. Counts exclude fixture setup.
"""

import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import statistics
from types import SimpleNamespace
import time

from redis.asyncio import Redis

from src.economy.tax_transactions import tax_key
from src.economy.taxes import utc_day
from src.operations.redis_sandbox import RedisSandbox
from src.repositories.player_repository import PlayerRepository
from src.utils.redis_config import RedisKeys
from src.config.game_config import RedisConfig


async def run(sandbox):
    async with Redis(host="127.0.0.1", port=sandbox.port, password=RedisConfig(password_file=sandbox.password_file).read_password(), decode_responses=True) as raw:
        repo = PlayerRepository(SimpleNamespace(redis=raw, hgetall=raw.hgetall))
        async with raw.pipeline(transaction=False) as pipe:
            for user in range(1, 501):
                pipe.hset(RedisKeys.player_position(user), mapping={"x": "50", "y": "50", "map": str((user - 1) % 50 + 1)})
                pipe.hset(RedisKeys.player_user_stats(user), mapping={"min_hp": "100"})
                pipe.hset(tax_key(user), mapping={"last_day": str(utc_day())})
            await pipe.execute()
        counts = Counter()
        execute_command, pipeline = raw.execute_command, raw.pipeline

        async def counted_command(*args, **kwargs):
            counts[args[0]] += 1
            return await execute_command(*args, **kwargs)

        def counted_pipeline(*args, **kwargs):
            pipe = pipeline(*args, **kwargs)
            execute = pipe.execute

            async def counted_execute(*args, **kwargs):
                counts.update(command[0][0] for command in pipe.command_stack)
                return await execute(*args, **kwargs)
            pipe.execute = counted_execute
            return pipe

        raw.execute_command, raw.pipeline = counted_command, counted_pipeline

        async def previous(ids):
            result = {}
            for user in ids:
                if await repo.is_alive(user):
                    position = await repo.get_position(user)
                    if position:
                        result[user] = position
            return result

        async def measure(operation):
            counts.clear()
            await operation()
            per_call = dict(counts)
            values = []
            for _ in range(31):
                started = time.perf_counter_ns()
                await operation()
                values.append((time.perf_counter_ns() - started) / 1000)
            values.sort()
            return {"p50_us": statistics.median(values), "p95_us": values[29], "p99_us": values[30], "samples": 31, "commands_per_call": per_call}

        results = []
        for count in (20, 50, 500):
            ids = list(range(1, count + 1))
            assert await previous(ids) == await repo.get_positions(ids, alive_only=True)
            results.append({"candidate_players": count, "previous": await measure(lambda: previous(ids)), "batched": await measure(lambda: repo.get_positions(ids, alive_only=True)), "batch_size": 256, "snapshots_retained_between_calls": False})
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with RedisSandbox() as sandbox:
        rows = asyncio.run(run(sandbox))
    root = Path(__file__).resolve().parents[1]
    report = {"python": platform.python_version(), "cases": rows, "source_hashes": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in ("src/repositories/player_mixins/_position_mixin.py", "src/services/npc/npc_ai_service.py", "src/effects/npc_ai_effect.py")}, "limitations": ["Already-settled daily balances, live candidates, loopback Redis", "Compares actual previous selection route and actual new batch method; no attack or transport", "500 candidates span two bounded pipelines; not 500 connected clients"]}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
