"""Measure the proposed item identity layout in an owned disposable Redis only.

This is a storage prototype for issue #334, not an implementation of durability.
No endpoint argument is accepted. No player or production data is read.
"""

import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import time

from src.operations.redis_sandbox import RedisSandbox

BATCH = 500
SLOTS = 30


def instance(index):
    return f"item:instance:{index:032x}"


def container(index):
    return f"study:inventory:{index // SLOTS + 1}"


def metadata(index):
    return {
        "item_id": "2",
        "created_at": "1800000000",
        "expires_at": "1802592000",
        "uses_spent": "0",
        "policy_version": "1",
        "owner_id": str(index // SLOTS + 1),
        "location": "inventory",
        "slot": str(index % SLOTS + 1),
    }


def percentiles(samples):
    ordered = sorted(samples)
    return {
        "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[math.ceil(len(ordered) * 0.95) - 1],
        "p99_ms": ordered[math.ceil(len(ordered) * 0.99) - 1],
        "samples": len(samples),
        "stdev_ms": statistics.stdev(samples),
    }


def measure(redis, count, individual):
    # FLUSHDB is restricted to the random container created inside main().
    redis.flushdb()
    baseline = redis.info("memory")
    before_aof = redis.info("persistence")["aof_current_size"]
    before_wire = redis.info("stats")
    started = time.perf_counter()
    for start in range(0, count, BATCH):
        with redis.pipeline(transaction=False) as pipe:
            for index in range(start, min(start + BATCH, count)):
                reference = f"i1:{index:032x}" if individual else "2:1"
                pipe.hset(container(index), f"slot_{index % SLOTS + 1}", reference)
                if individual:
                    pipe.hset(instance(index), mapping=metadata(index))
            pipe.execute()
    redis.execute_command("WAITAOF", 1, 0, 5000)
    creation = time.perf_counter() - started
    memory = redis.info("memory")
    after_aof = redis.info("persistence")["aof_current_size"]
    wire = redis.info("stats")
    keys = [f"study:inventory:{i + 1}" for i in range(math.ceil(count / SLOTS))]
    if individual:
        keys += [instance(i) for i in range(count)]
    usage = 0
    for start in range(0, len(keys), BATCH):
        with redis.pipeline(transaction=False) as pipe:
            for key in keys[start : start + BATCH]:
                pipe.memory_usage(key, samples=0)
            usage += sum(pipe.execute())
    reads, changes, cpu = [], [], time.process_time()
    for sample in range(101):
        owner = sample % (count // SLOTS)
        first = owner * SLOTS
        started = time.perf_counter()
        values = redis.hmget(container(first), [f"slot_{i + 1}" for i in range(SLOTS)])
        if individual:
            with redis.pipeline(transaction=False) as pipe:
                for value in values:
                    identity = value.removeprefix("i1:")
                    pipe.hmget(
                        "item:instance:" + identity,
                        "item_id",
                        "created_at",
                        "expires_at",
                        "uses_spent",
                        "policy_version",
                    )
                rows = pipe.execute()
            if any(row[0] != "2" for row in rows):
                raise AssertionError("A reference lost its metadata")
        elif any(value != "2:1" for value in values):
            raise AssertionError("Invalid baseline inventory")
        reads.append((time.perf_counter() - started) * 1000)
        if individual:
            started = time.perf_counter()
            # Measures one metadata mutation, not the complete combat transaction.
            redis.hincrby(instance(first), "uses_spent", 1)
            changes.append((time.perf_counter() - started) * 1000)
    return {
        "objects": count,
        "layout": "individual-prototype" if individual else "current-slots",
        "key_count": len(keys),
        "sum_memory_usage_bytes": usage,
        "memory_usage_bytes_per_object": usage / count,
        "used_memory_delta_bytes": memory["used_memory"] - baseline["used_memory"],
        "redis_rss_bytes": memory["used_memory_rss"],
        "aof_growth_bytes": after_aof - before_aof,
        "creation_seconds": creation,
        "creation_objects_per_second": count / creation,
        "creation_wire_input_bytes": wire["total_net_input_bytes"]
        - before_wire["total_net_input_bytes"],
        "creation_wire_output_bytes": wire["total_net_output_bytes"]
        - before_wire["total_net_output_bytes"],
        "container_read": percentiles(reads),
        "one_metadata_update": percentiles(changes) if changes else None,
        "read_update_client_cpu_seconds": time.process_time() - cpu,
        "metadata_encoding": redis.object("encoding", instance(0)) if individual else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with RedisSandbox() as sandbox, sandbox.client() as redis:
        version = redis.info("server")["redis_version"]
        for count in (1000, 100000):
            for individual in (False, True):
                row = measure(redis, count, individual)
                rows.append(row)
                print(
                    count, row["layout"], round(row["memory_usage_bytes_per_object"], 2), flush=True
                )
    report = {
        "schema": 1,
        "issue": 334,
        "redis": version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "synthetic_only": True,
        "production_data_used": False,
        "production_durability_enabled": False,
        "rows": rows,
        "limitations": [
            "one host and one prototype layout, not production capacity",
            "101 warm container reads; startup and cold page cache are not measured",
            "RSS includes allocator history; use MEMORY USAGE for stored-key comparisons",
            "creation uses pipelines; it does not model per-action WATCH/EXEC and WAITAOF cost",
            "timestamps and the example lifetime describe payload size, not proposed balance defaults",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
