#!/usr/bin/env python3
"""Reproducible structure audit; synthetic entities and optional disposable Redis only."""

import argparse
import dataclasses
import gc
import hashlib
import json
import platform
import resource
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

from src.game.ground_item_index import GroundItemIndex
from src.game.npc_index import NpcIndex
from src.game.player_index import PlayerIndex
from src.game.tile_occupation import TileOccupation
from src.models.npc import NPC
from src.services.map.map_bitmap import TileBitmap
from src.services.map.map_resources_service import MapResourcesService
from src.utils.ground_state import GroundState, stack_identity


def deep_bytes(value, seen=None):
    """Count owned Python containers without counting shared objects twice."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        size += sum(deep_bytes(k, seen) + deep_bytes(v, seen) for k, v in value.items())
    elif isinstance(value, (list, tuple, set, frozenset)):
        size += sum(deep_bytes(v, seen) for v in value)
    elif hasattr(value, "__dict__"):
        size += deep_bytes(vars(value), seen)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        size += sum(
            deep_bytes(getattr(value, field.name), seen) for field in dataclasses.fields(value)
        )
    return size


def extra_bytes(base, extra):
    seen = set()
    deep_bytes(base, seen)
    return deep_bytes(extra, seen)


def npc_model_footprint():
    records = [
        NPC(
            npc_id=1,
            char_index=i + 10001,
            instance_id=f"npc-{i}",
            map_id=1,
            x=i % 100 + 1,
            y=i // 100 + 1,
            heading=3,
            name="Fixture",
            description="Synthetic",
            body_id=1,
            head_id=0,
            hp=100,
            max_hp=100,
            level=1,
            is_hostile=True,
            is_attackable=True,
        )
        for i in range(1000)
    ]
    size = deep_bytes(records)
    return {
        "records": len(records),
        "owned_python_bytes": size,
        "bytes_per_record_including_list": size / len(records),
        "excludes": "Redis, network, maps and renderer",
    }


def measure(operation, *, repeats=31, loops=10):
    for _ in range(3):
        operation()
    samples = []
    for _ in range(repeats):
        started = time.perf_counter_ns()
        for _ in range(loops):
            operation()
        samples.append((time.perf_counter_ns() - started) / loops / 1000)
    ordered = sorted(samples)
    return {
        "unit": "microseconds_per_operation",
        "p50": statistics.median(samples),
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "p99": ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))],
        "repeats": repeats,
        "loops_per_sample": loops,
    }


def allocations(operation):
    gc.collect()
    tracemalloc.start()
    result = operation()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"retained_bytes": current, "peak_bytes": peak, "result_length": len(result)}


def entities(count, maps):
    occupied = TileOccupation()
    players = PlayerIndex(occupied)
    npcs = NpcIndex(occupied)
    ground = GroundItemIndex(10)
    for identity in range(count):
        mid = identity % maps + 1
        coordinate = identity // maps
        x, y = coordinate % 100 + 1, coordinate // 100 + 1
        players.add_player(mid, identity + 1, None, f"Player{identity}")
        npc = SimpleNamespace(
            instance_id=f"npc-{identity}",
            char_index=identity + 10001,
            name=f"NPC{identity}",
            x=x,
            y=y,
        )
        npcs.add_npc(mid, npc)
        ground.add_ground_item(mid, x, y, {"item_id": 15, "quantity": 1})
    last_map = (count - 1) % maps + 1
    last_index = count - 1 + 10001
    by_id = {
        uid: (sender, name)
        for row in players.players_by_map.values()
        for uid, (sender, name) in row.items()
    }
    by_name = {name.casefold(): uid for uid, (_sender, name) in by_id.items()}
    by_character = {
        (mid, npc.char_index): npc for mid, row in npcs.npcs_by_map.items() for npc in row.values()
    }
    by_ground_map = {}
    for (mid, x, y), row in ground.ground_items.items():
        by_ground_map.setdefault(mid, {})[x, y] = row
    unique = lambda: list(
        dict.fromkeys(uid for row in players.players_by_map.values() for uid in row)
    )
    assert unique() == players.get_all_connected_user_ids()
    assert by_character[last_map, last_index] is npcs.get_npc_by_char_index(last_map, last_index)
    return {
        "entities": count,
        "maps": maps,
        "layout": "concentrated" if maps == 1 else "distributed",
        "operations": {
            "player_unique_ids_current": measure(players.get_all_connected_user_ids),
            "player_unique_ids_ordered_hash": measure(unique),
            "player_find_name_current": measure(
                lambda: players.find_player_by_username(f"Player{count - 1}")
            ),
            "player_find_name_hash": measure(lambda: by_name.get(f"player{count - 1}")),
            "npc_find_character_current": measure(
                lambda: npcs.get_npc_by_char_index(last_map, last_index)
            ),
            "npc_find_character_hash": measure(lambda: by_character.get((last_map, last_index))),
            "ground_count_map_current": measure(lambda: ground.get_ground_items_count(last_map)),
            "ground_count_map_bucket": measure(
                lambda: sum(len(v) for v in by_ground_map[last_map].values())
            ),
            "tile_lookup": measure(lambda: occupied.get_occupant(last_map, 1, 1)),
        },
        "owned_bytes": {
            "player_index": deep_bytes(players),
            "npc_index_including_synthetic_records_and_tiles": deep_bytes(npcs),
            "tile_index": deep_bytes(occupied),
            "ground_index": deep_bytes(ground),
            "incremental_player_id_index": extra_bytes(players, by_id),
            "incremental_player_name_index": extra_bytes(players, by_name),
            "incremental_npc_character_index": extra_bytes(npcs, by_character),
            "incremental_ground_map_buckets": extra_bytes(ground, by_ground_map),
        },
        "unique_ids_allocations": allocations(players.get_all_connected_user_ids),
    }


def ground_document(count):
    values = {
        f"{i % 100 + 1},{i // 100 + 1}": [
            {"item_id": 15, "quantity": 1, "stack_id": stack_identity(f"fixture:{i}")}
        ]
        for i in range(count)
    }
    raw = json.dumps(values, separators=(",", ":"))

    def change():
        state = GroundState(1, raw)
        state.append(100, 100, {"item_id": 15, "quantity": 1, "stack_id": stack_identity("extra")})
        return state.encode()

    result = {
        "positions": count,
        "json_bytes": len(raw.encode()),
        "read_validate_modify_encode": measure(change, repeats=21, loops=1),
        "allocations": allocations(change),
        "bytes_read_plus_written_per_commit_lower_bound": len(raw.encode()) * 2,
    }
    return result, raw


def terrain():
    started = time.perf_counter()
    maps = MapResourcesService()
    loaded = time.perf_counter() - started
    layers = ("blocked", "water", "trees", "mines", "anvils", "forges")
    count = sum(len(row.get(layer, ())) for row in maps.resources.values() for layer in layers)
    planes = [bytearray(1250) for _row in maps.resources for _layer in layers]
    flags = [bytearray(10000) for _row in maps.resources]
    sparse = {(1, 1), (100, 100)}
    unadapted = TileBitmap.from_set(sparse)
    adapted = TileBitmap.from_set({(x - 1, y - 1) for x, y in sparse})
    assert not unadapted.get(100, 100)
    assert all(adapted.get(x - 1, y - 1) for x, y in sparse)
    return {
        "maps": len(maps.resources),
        "coordinates_across_six_layers": count,
        "load_seconds": loaded,
        "resource_python_bytes": deep_bytes(maps.resources),
        "six_bit_planes_python_bytes": deep_bytes(planes),
        "six_bit_planes_payload_bytes": len(planes) * 1250,
        "one_byte_flags_python_bytes": deep_bytes(flags),
        "one_byte_flags_payload_bytes": len(flags) * 10000,
        "bitmap_requires_1_based_to_0_based_adapter": True,
        "baseline_bitmap_drops_100_100_without_adapter": True,
    }


def redis_workloads(documents):
    from src.operations.redis_sandbox import RedisSandbox

    with RedisSandbox() as sandbox, sandbox.client() as redis:
        baseline_bytes = redis.info("memory")["used_memory"]
        for i in range(1000):
            redis.hset(f"player:{i}:fixture", mapping={"hp": "100", "x": "50", "y": "50"})

        def sequential():
            return [redis.hgetall(f"player:{i}:fixture") for i in range(50)]

        def pipelined():
            with redis.pipeline(transaction=False) as pipe:
                for i in range(50):
                    pipe.hgetall(f"player:{i}:fixture")
                return pipe.execute()

        assert sequential() == pipelined()
        results = {
            "redis": redis.info("server")["redis_version"],
            "sequential_50_hashes": measure(sequential, repeats=21, loops=1),
            "pipeline_50_hashes": measure(pipelined, repeats=21, loops=1),
            "commands_both": 50,
            "application_round_trips": {"sequential": 50, "pipeline": 1},
            "ground": [],
            "minimal_player_hash_count": 1000,
            "minimal_player_hash_used_memory_delta": redis.info("memory")["used_memory"]
            - baseline_bytes,
        }
        for count, raw in documents:
            key = "fixture:ground"
            redis.set(key, raw)

            def actual_document_roundtrip():
                with redis.pipeline() as pipe:
                    pipe.watch(key)
                    state = GroundState(1, pipe.get(key))
                    pipe.multi()
                    pipe.set(key, state.encode())
                    pipe.execute()

            results["ground"].append(
                {
                    "positions": count,
                    "watch_get_validate_set_exec": measure(
                        actual_document_roundtrip, repeats=21, loops=1
                    ),
                    "excludes_gameplay_aof_ack_and_receipt": True,
                }
            )
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--redis", action="store_true")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sizes = (100, 1000) if args.quick else (100, 1000, 5000)
    result = {
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_hashes": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (
                "src/game/player_index.py",
                "src/game/npc_index.py",
                "src/game/ground_item_index.py",
                "src/game/tile_occupation.py",
            )
        },
        "gc_enabled": gc.isenabled(),
        "limitations": [
            "Microbenchmarks, not production capacity",
            "Python sizes deduplicate owned objects; incremental index sizes exclude referents already owned by the original index, not allocator RSS",
            "Synthetic NPC records exclude renderer/network/account overhead",
            "No performance gates based on wall clock on shared CI",
        ],
        "entities": [entities(count, maps) for count in sizes for maps in (1, 50)],
        "terrain": terrain(),
        "npc_model": npc_model_footprint(),
        "ground_documents": [],
    }
    documents = []
    for count in sizes:
        record, raw = ground_document(count)
        result["ground_documents"].append(record)
        documents.append((count, raw))
    if args.redis:
        result["redis"] = redis_workloads(documents)
    result["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
