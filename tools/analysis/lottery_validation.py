"""Frecuencias reproducibles del algoritmo productivo, con semillas sólo de fixture."""

import argparse
import json
import math
from pathlib import Path
import random

from src.services.lottery.rules import choose, commitment, draw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rng = random.Random(576)
    samples = 200000
    wins = 0
    for _ in range(samples):
        seed = rng.getrandbits(256).to_bytes(32, "big").hex()
        wins += draw(seed, "1" * 32, "2" * 64, 396) < 99
    rows = {"1": {"net": 99}, "2": {"net": 297}}
    seed = "00" * 32
    number = draw(seed, "1" * 32, "2" * 64, 396)
    observed = wins / samples
    half = 1.96 * math.sqrt(observed * (1 - observed) / samples)
    report = {
        "schema": 1,
        "issues": [571, 572, 573, 574, 575, 576],
        "samples": samples,
        "fixture_seed": 576,
        "expected_first": 0.25,
        "wins_first": wins,
        "observed_first": observed,
        "observed_normal_95_interval": [observed - half, observed + half],
        "production_seed_source": "secrets.token_hex(32); PRNG used only by this fixture",
        "algorithm": "HMAC-SHA256 with rejection sampling; cumulative net intervals",
        "vector": {
            "seed": seed,
            "commitment": commitment(seed),
            "round": "1" * 32,
            "snapshot_hash": "2" * 64,
            "pool": 396,
            "number": number,
            "winner": choose(rows, number),
        },
        "boundaries": [{"number": n, "winner": choose(rows, n)} for n in (0, 98, 99, 395)],
        "limitations": [
            "The deterministic simulation does not prove cryptographic fairness.",
            "Persistence and live gameplay are exercised separately with owned Redis/AOF and two graphical Godot processes.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "samples": samples,
                "observed_first": observed,
                "interval": report["observed_normal_95_interval"],
            }
        )
    )


if __name__ == "__main__":
    main()
