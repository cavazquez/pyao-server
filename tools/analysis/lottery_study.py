"""Storage and interval prototype for #403; does not enable a game lottery."""

import argparse
from bisect import bisect_right
import hashlib
from itertools import accumulate
import json
import math
from pathlib import Path
import platform
import random
import statistics
import time

from src.operations.redis_sandbox import RedisSandbox


def fee(gross):
    return (gross + 99) // 100


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(403)
    ends = [99, 396]
    vectors = [{"number": n, "winner_index": bisect_right(ends, n)} for n in (0, 98, 99, 395)]
    if [row["winner_index"] for row in vectors] != [0, 0, 1, 1]:
        raise AssertionError("Incorrect interval boundaries")
    if sum(fee(i) - fee(i - 1) for i in range(1, 301)) != fee(300):
        raise AssertionError("Splitting changes the cumulative fee")
    samples = 200000
    wins = sum(bisect_right(ends, rng.randrange(396)) == 0 for _ in range(samples))
    rows = []
    with RedisSandbox() as sandbox, sandbox.client() as redis:
        version = redis.info("server")["redis_version"]
        for size in (1, 128, 4096):
            participants = [(i + 1, 100 * (1 + i % 20)) for i in range(size)]
            rng.shuffle(participants)
            mapping = {
                str(uid): json.dumps(
                    {"gross": gross, "fee": fee(gross), "net": gross - fee(gross)},
                    separators=(",", ":"),
                )
                for uid, gross in participants
            }
            key = f"study:lottery:participants:{size}"
            redis.hset(key, mapping=mapping)
            builds = []
            for _ in range(101):
                started = time.perf_counter_ns()
                ordered = sorted(participants)
                prefixes = list(accumulate(gross - fee(gross) for _uid, gross in ordered))
                builds.append(time.perf_counter_ns() - started)
            numbers = [rng.randrange(prefixes[-1]) for _ in range(10000)]
            started = time.perf_counter_ns()
            chosen = [bisect_right(prefixes, number) for number in numbers]
            lookup_ns = (time.perf_counter_ns() - started) / len(numbers)
            if any(index >= size for index in chosen):
                raise AssertionError("A draw left the participant intervals")
            rows.append(
                {
                    "participants": size,
                    "redis_participant_hash_bytes": redis.memory_usage(key, samples=0),
                    "json_payload_bytes": sum(len(k) + len(v) for k, v in mapping.items()),
                    "prefix_build_p50_ns": statistics.median(builds),
                    "prefix_build_p95_ns": sorted(builds)[95],
                    "interval_lookup_mean_ns": lookup_ns,
                    "draw_lookup_samples": len(numbers),
                }
            )
    expected = 0.25
    report = {
        "schema": 1,
        "issue": 403,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "redis": version,
        "platform": platform.platform(),
        "rows": rows,
        "vectors_100_plus_300": vectors,
        "gross": 400,
        "fee": 4,
        "pool": 396,
        "simulation": {
            "seed": 403,
            "samples": samples,
            "wins_first": wins,
            "observed_first": wins / samples,
            "expected_first": expected,
            "normal_95_half_width": 1.96 * math.sqrt(expected * (1 - expected) / samples),
        },
        "production_data_used": False,
        "lottery_enabled": False,
        "limitations": [
            "stdlib PRNG is used only for a repeatable simulation, not the proposed production RNG",
            "simulation does not prove cryptographic fairness or payment durability",
            "Redis measurements include only participants, excluding receipts, round metadata and AOF",
            "single development host with other tests; timings are not a production SLA",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
