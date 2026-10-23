"""Compare actual old/new pet and campfire paths in an owned, disposable Redis.

python -m tools.analysis.world_index_study --output /tmp/world-index-study.json
The baseline is read from Git, never downloaded or executed from an issue body.
"""

import argparse
import asyncio
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import tempfile
import time
import tracemalloc
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.config.game_config import RedisConfig
from src.effects.effect_pet_follow import PetFollowEffect
from src.game.map_manager import MapManager
from src.messaging.senders.message_status_effects_sender import StatusEffectsMessageSender
from src.models.npc import NPC
from src.operations.redis_sandbox import RedisSandbox
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.services.npc.summon_service import SummonService
from tools.analysis.interpreter_study import percentile, runtime_metadata

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "fd3d819e75116ac6a4a6fcace7c6970e945425b9"
SOURCES = (
    "src/repositories/npc_repository.py",
    "src/services/npc/summon_service.py",
    "src/effects/effect_pet_follow.py",
    "src/messaging/senders/message_status_effects_sender.py",
)


def legacy_modules(directory, revision):
    modules, hashes = {}, {}
    for source in SOURCES:
        content = subprocess.check_output(["git", "show", f"{revision}:{source}"], cwd=ROOT)
        name = Path(source).stem
        path = directory / f"legacy_{name}.py"
        path.write_bytes(content)
        spec = importlib.util.spec_from_file_location(f"study_legacy_{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
        hashes[source] = hashlib.sha256(content).hexdigest()
    return modules, hashes


async def measure(raw, operation, samples):
    for _ in range(3):
        await operation()
    previous = await raw.info("commandstats")
    await operation()
    after = await raw.info("commandstats")
    commands = {
        key.removeprefix("cmdstat_"): data["calls"] - previous.get(key, {}).get("calls", 0)
        for key, data in after.items()
        if data["calls"] - previous.get(key, {}).get("calls", 0) and key != "cmdstat_info"
    }
    previous_cpu = await raw.info("cpu")
    wall, cpu = [], []
    for _ in range(samples):
        started, process = time.perf_counter_ns(), time.process_time_ns()
        await operation()
        wall.append((time.perf_counter_ns() - started) / 1000)
        cpu.append((time.process_time_ns() - process) / 1000)
    after_cpu = await raw.info("cpu")
    tracemalloc.start()
    await operation()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "samples": samples,
        "wall_us": {
            name: percentile(wall, value)
            for name, value in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))
        },
        "wall_us_mean": statistics.mean(wall),
        "wall_us_stdev": statistics.stdev(wall),
        "client_cpu_us_per_call": statistics.mean(cpu),
        "redis_cpu_us_per_call": sum(
            after_cpu[key] - previous_cpu[key] for key in ("used_cpu_sys", "used_cpu_user")
        )
        * 1e6
        / samples,
        "commands_per_call": commands,
        "python_traced_peak_bytes_one_call": peak,
        "process_peak_rss_bytes_cumulative": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * 1024,
    }


async def run(sandbox, legacy, samples):
    from src.utils.redis_client import RedisClient

    client = RedisClient()
    await client.connect(
        RedisConfig(host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file),
        seed_defaults=False,
    )
    raw = client.redis
    rows = []
    try:
        base = NPC(1, 10001, "probe-0", 2, 1, 1, 3, "Probe", "", 1, 0, 100, 100, 1, False, True)
        for total, foreign in ((32, 0), (512, 10000), (4096, 50000)):
            # The database belongs only to this sandbox. Both variants use identical data.
            await raw.flushdb()
            maps = MapManager()
            maps.add_player(1, 1, object(), "Probe")
            dataset = hashlib.sha256()
            async with raw.pipeline(transaction=False) as pipe:
                for number in range(total):
                    pet = number < 3
                    npc = replace(
                        base,
                        instance_id=f"probe-{number}",
                        char_index=10001 + number,
                        map_id=1 if pet else 2,
                        x=1 + number % 100,
                        y=10 if pet else 20 + number // 100,
                        summoned_by_user_id=1 if pet else 0,
                        summoned_until=time.time() + 3600 if pet else 0,
                    )
                    maps.add_npc(npc.map_id, npc)
                    data = {key: str(value) for key, value in asdict(npc).items()}
                    dataset.update(json.dumps(data, sort_keys=True).encode())
                    pipe.hset(f"npc:instance:{npc.instance_id}", mapping=data)
                    if pet:
                        pipe.sadd("player:1:pets", npc.instance_id)
                for number in range(foreign):
                    pipe.set(f"unrelated:{number}", "x" * 32)
                for number in range(202):
                    map_id = 1 if number < 2 else 3 + number
                    key = f"world:campfire:{map_id}:50:{50 + number % 2}"
                    pipe.hset(
                        key,
                        mapping={
                            "x": "50",
                            "y": str(50 + number % 2),
                            "until": str(time.time() + 3600),
                        },
                    )
                    pipe.sadd(f"world:campfires:{map_id}", key)
                pipe.hset(
                    "player:1:position", mapping={"map": "1", "x": "2", "y": "10", "heading": "3"}
                )
                pipe.hset("player:1:user_stats", mapping={"min_hp": "100", "max_hp": "100"})
                await pipe.execute()
            old_repo = legacy["npc_repository"].NPCRepository(client)
            new_repo, players = NPCRepository(client), PlayerRepository(client)
            old_summon = legacy["summon_service"].SummonService(old_repo, players)
            new_summon = SummonService(new_repo, players)
            old_follow = legacy["effect_pet_follow"].PetFollowEffect(
                SimpleNamespace(npc_repository=old_repo, map_manager=maps), interval_seconds=0
            )
            new_follow = PetFollowEffect(
                SimpleNamespace(npc_repository=new_repo, map_manager=maps), interval_seconds=0
            )
            sender = SimpleNamespace(send=AsyncMock(), address="study")
            old_fires = legacy["message_status_effects_sender"].StatusEffectsMessageSender(sender)
            new_fires = StatusEffectsMessageSender(sender)

            async def old_cleanup():
                ids = await old_summon.remove_all_player_pets(1)
                all_npcs = await old_repo.get_all_npcs()
                return [
                    next(npc for npc in all_npcs if npc.instance_id == identity) for identity in ids
                ]

            async def new_cleanup():
                ids = await new_summon.remove_all_player_pets(1)
                return [maps.get_npc_by_instance(identity) for identity in ids]

            assert sorted(await old_summon.get_player_pets(1)) == sorted(
                await new_summon.get_player_pets(1)
            )
            assert {npc.instance_id for npc in await old_cleanup()} == {
                npc.instance_id for npc in await new_cleanup()
            }
            cases = {
                "owner_query": (
                    lambda: old_summon.get_player_pets(1),
                    lambda: new_summon.get_player_pets(1),
                ),
                "follow_tick": (
                    lambda: old_follow.apply(1, players, None),
                    lambda: new_follow.apply(1, players, None),
                ),
                "disconnect_discovery": (old_cleanup, new_cleanup),
                "campfire_sync": (
                    lambda: old_fires.sync_campfires(1, players),
                    lambda: new_fires.sync_campfires(1, players),
                ),
            }
            measured = {}
            for name, (before, after) in cases.items():
                measured[name] = {
                    "before": await measure(raw, before, samples),
                    "after": await measure(raw, after, samples),
                }
            assert old_fires._campfires == new_fires._campfires == {(50, 50), (50, 51)}
            info = await raw.info()
            rows.append(
                {
                    "npcs": total,
                    "owner_pets": 3,
                    "foreign_keys": foreign,
                    "players": 1,
                    "campfires_same_map": 2,
                    "campfires_other_maps": 200,
                    "fixture_npc_hash": dataset.hexdigest(),
                    "redis_version": info["redis_version"],
                    "redis_used_memory_bytes": info["used_memory"],
                    "pet_index_bytes": await raw.memory_usage("player:1:pets"),
                    "campfire_map_index_bytes": await raw.memory_usage("world:campfires:1"),
                    "cases": measured,
                }
            )
            print(json.dumps({"completed_npcs": total}), flush=True)
        return rows
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--samples", type=int, default=31)
    args = parser.parse_args()
    if not 3 <= args.samples <= 101:
        parser.error("samples must be 3..101")
    with tempfile.TemporaryDirectory(prefix="pyao-index-baseline-") as directory:
        legacy, old_hashes = legacy_modules(Path(directory), args.baseline)
        with RedisSandbox() as sandbox:
            rows = asyncio.run(run(sandbox, legacy, args.samples))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "runtime": runtime_metadata(),
                "platform": platform.platform(),
                "baseline_commit": args.baseline,
                "baseline_source_sha256": old_hashes,
            "current_source_sha256": {
                str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((ROOT / "src").rglob("*.py"))
            },
                "cases": rows,
                "limitations": [
                    "Loopback, deterministic small owner/map scope, not a player capacity test",
                    "Disconnect discovery excludes deletion/transport equally in both variants",
                    "Warm files; no OS page cache purge; RSS is process-wide cumulative peak",
                    "Python traced allocation peak excludes native/Redis memory; Redis INFO CPU includes background work",
                    "Sequential before/after samples; repeat on dedicated hardware for small differences",
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(args.output)


if __name__ == "__main__":
    main()
