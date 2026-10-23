"""Compare full servers over TLS with identical inputs and owned Redis/AOF.

Fresh processes on a warm filesystem. Eight concurrent players, one slow reader,
five seconds warm-up and twenty measured seconds; repeated/rotated variants.
The graphical gameplay checks remain separate from these bounded load samples.
"""

import argparse
import asyncio
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import statistics
import subprocess
import sys
import tempfile
import time

from src.config.game_config import RedisConfig
from src.operations.redis_sandbox import RedisSandbox
from src.repositories.account_repository import AccountRepository
from src.repositories.player_repository import PlayerRepository
from src.utils.password_utils import hash_password
from src.utils.redis_client import RedisClient
from tools.analysis.interpreter_study import runtime_metadata
from tools.analysis.nuitka_study import ROOT, source_hashes


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def wait_server(process, endpoint):
    started = time.monotonic()
    while time.monotonic() - started < 120:
        if process.poll() is not None:
            raise RuntimeError("Server exited before listening; inspect trial/server.log")
        try:
            with socket.create_connection(("127.0.0.1", endpoint), timeout=0.2):
                return time.monotonic() - started
        except OSError:
            time.sleep(0.02)
    raise TimeoutError("Server did not listen within 120 seconds")


async def seed(settings, password_hash, password, count):
    client = RedisClient()
    await client.connect(settings, seed_defaults=False)
    try:
        accounts, players = AccountRepository(client), PlayerRepository(client)
        profiles = []
        for number in range(count):
            name = f"Study{number:03d}"
            uid = await accounts.create_account(
                name,
                password_hash,
                "study@example.invalid",
                {"race": 1, "gender": 1, "job": 1, "head": 1, "home": 1},
            )
            await players.set_position(uid, 20 + number, 64, 2, 3)
            await players.set_attributes(
                uid, strength=20, agility=20, intelligence=20, charisma=20, constitution=20
            )
            await players.set_stats(
                uid,
                min_hp=30000,
                max_hp=30000,
                min_mana=30000,
                max_mana=30000,
                min_sta=30000,
                max_sta=30000,
                gold=1000,
                level=40,
                elu=9999999,
                experience=0,
            )
            await players.set_skills(uid, magia=90)
            profiles.append({"username": name, "password": password})
        return profiles
    finally:
        await client.disconnect()


def summarize(rows):
    result = {}
    for variant in sorted({row["variant"] for row in rows}):
        trials = [row for row in rows if row["variant"] == variant]
        fields = {
            "startup_seconds": [row["startup_seconds"] for row in trials],
            "rtt_p50_ms": [row["benchmark"]["rtt_ms"]["p50"] for row in trials],
            "rtt_p95_ms": [row["benchmark"]["rtt_ms"]["p95"] for row in trials],
            "rtt_p99_ms": [row["benchmark"]["rtt_ms"]["p99"] for row in trials],
            "login_p50_ms": [row["benchmark"]["login_ms"]["p50"] for row in trials],
            "server_cpu_seconds": [row["server_cpu_seconds"] for row in trials],
            "server_rss_peak_bytes": [row["server_rss_peak_bytes"] for row in trials],
            "operations_per_second": [row["operations_per_second"] for row in trials],
        }
        result[variant] = {
            field: {
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            }
            for field, values in fields.items()
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seconds", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--connections", type=int, default=8)
    args = parser.parse_args()
    if (
        not 2 <= args.repeats <= 10
        or not 10 <= args.seconds <= 120
        or not 2 <= args.connections <= 32
    ):
        parser.error("repeats=2..10, seconds=10..120, connections=2..32")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    variants = [("cpython", [sys.executable, "-m", "src.run_server"])]
    for path in args.build:
        build = json.loads(path.read_text())
        if (
            build.get("exit_code") != 0
            or not build.get("source_unchanged_during_build")
            or build["source_sha256"] != source_hashes()
        ):
            raise RuntimeError(f"Candidate does not match sources: {path}")
        binary = Path(build["executable"])
        if (
            hashlib.file_digest(binary.open("rb"), "sha256").hexdigest()
            != build["executable_sha256"]
        ):
            raise RuntimeError("Candidate hash mismatch")
        variants.append((build["mode"], [str(binary)]))
    rows = []
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "runtime": runtime_metadata(),
        "source_sha256": source_hashes(),
        "repeats": args.repeats,
        "connections": args.connections,
        "warmup_seconds": args.warmup,
        "measured_seconds": args.seconds,
        "trials": rows,
        "limits": [
            "Loopback TLS and isolated Redis/AOF, not maximum capacity",
            "OS page cache not flushed; startup is fresh process with common pre-extracted map files",
            "Same logical players, maps, items/config; world NPC UUIDs and game RNG vary normally",
            "Movement/chat/ping load plus actual background ticks; combat/serialization kernels and graphical gameplay are separate",
            "CPU interval excludes login/startup; RSS is sampled every 0.5 seconds",
        ],
    }
    password = secrets.token_urlsafe(20)
    password_hash = hash_password(password)
    with (
        tempfile.TemporaryDirectory(prefix="pyao-nuitka-network-") as temporary,
        RedisSandbox() as sandbox,
    ):
        work = Path(temporary)
        certificate, key = work / "ca.crt", work / "key.pem"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=IP:127.0.0.1,DNS:localhost",
                "-keyout",
                str(key),
                "-out",
                str(certificate),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        key.chmod(0o600)
        settings = RedisConfig(
            host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file
        )
        for repeat in range(args.repeats):
            order = variants[repeat % len(variants) :] + variants[: repeat % len(variants)]
            for name, entry in order:
                trial = output / f"{repeat}-{name}"
                trial.mkdir()
                with sandbox.client() as store:
                    store.flushdb()
                    store.set("config:effects:gold_decay:enabled", "0")
                    cpu_before = store.info("cpu")
                endpoint = port()
                environment = {
                    key: value
                    for key, value in os.environ.items()
                    if not key.startswith(("PYAO_", "SNAP"))
                }
                environment.update(
                    PYTHONPATH=str(ROOT),
                    PYTHONNOUSERSITE="1",
                    PYTHONUNBUFFERED="1",
                    PYAO_REDIS__HOST="127.0.0.1",
                    PYAO_REDIS__PORT=str(sandbox.port),
                    PYAO_REDIS__PASSWORD_FILE=str(sandbox.password_file),
                    PYAO_STATE_DIR=str(work / f"state-{repeat}-{name}"),
                    PYAO_METRICS_FILE=str(trial / "ticks.json"),
                    PYAO_SECURITY__AUTH_ATTEMPTS_PER_IP="400",
                    PYAO_SECURITY__AUTH_ATTEMPTS_PER_ACCOUNT="100",
                )
                command = [
                    *entry,
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(endpoint),
                    "--ssl",
                    "--ssl-cert",
                    str(certificate),
                    "--ssl-key",
                    str(key),
                    "--config-file",
                    str(ROOT / "config/server.toml"),
                    "--data-dir",
                    str(ROOT / "data"),
                    "--maps-dir",
                    str(ROOT / "map_data"),
                ]
                with (trial / "server.log").open("wb") as log:
                    process = subprocess.Popen(
                        command, cwd=work, env=environment, stdout=log, stderr=subprocess.STDOUT
                    )
                    try:
                        startup = wait_server(process, endpoint)
                        profiles = asyncio.run(
                            seed(settings, password_hash, password, args.connections + 1)
                        )
                        credentials = work / "accounts.json"
                        credentials.write_text(json.dumps(profiles))
                        credentials.chmod(0o600)
                        common = [
                            sys.executable,
                            "-m",
                            "tools.benchmark",
                            "--accounts",
                            str(credentials),
                            "--connections",
                            str(args.connections),
                            "--slow-readers",
                            "1",
                            "--cadence",
                            ".10",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(endpoint),
                            "--pid",
                            str(process.pid),
                            "--ca",
                            str(certificate),
                            "--metrics",
                            str(trial / "ticks.json"),
                        ]
                        for label, seconds in (("warmup", args.warmup), ("measured", args.seconds)):
                            subprocess.run(
                                [
                                    *common,
                                    "--seconds",
                                    str(seconds),
                                    "--output",
                                    str(trial / f"{label}.json"),
                                ],
                                cwd=ROOT,
                                env=environment,
                                check=True,
                                stdout=subprocess.DEVNULL,
                                timeout=120,
                            )
                            if label == "warmup":
                                time.sleep(
                                    0.5
                                )  # allow owned sessions to release before the next login
                        measured = json.loads((trial / "measured.json").read_text())
                        if not measured["passed"] or measured["errors"]:
                            raise RuntimeError("Benchmark functional failure")
                        samples = measured["server_process"]
                        with sandbox.client() as store:
                            cpu_after = store.info("cpu")
                            commands = store.info("commandstats")
                            npcs = len(list(store.scan_iter("npc:instance:*")))
                        row = {
                            "variant": name,
                            "repeat": repeat,
                            "startup_seconds": startup,
                            "benchmark": measured,
                            "server_cpu_seconds": samples[-1]["cpu_seconds"]
                            - samples[0]["cpu_seconds"],
                            "server_cpu_interval_seconds": samples[-1]["time"] - samples[0]["time"],
                            "server_rss_peak_bytes": max(sample["rss_bytes"] for sample in samples),
                            "operations_per_second": measured["rtt_ms"]["samples"]
                            / measured["seconds"],
                            "redis_cpu_seconds_whole_trial": sum(
                                cpu_after[field] - cpu_before[field]
                                for field in ("used_cpu_sys", "used_cpu_user")
                            ),
                            "redis_commands_cumulative": commands,
                            "world_npcs_after": npcs,
                        }
                        rows.append(row)
                        report["summary"] = summarize(rows)
                        (output / "network.json").write_text(json.dumps(report, indent=2) + "\n")
                        print(
                            json.dumps(
                                {
                                    "variant": name,
                                    "repeat": repeat,
                                    "p95_ms": measured["rtt_ms"]["p95"],
                                    "cpu_seconds": row["server_cpu_seconds"],
                                }
                            ),
                            flush=True,
                        )
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=20)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                    if process.returncode != 0:
                        raise RuntimeError(
                            f"Non-graceful server shutdown: {name}, code={process.returncode}"
                        )
                    if "Traceback (most recent call last)" in (trial / "server.log").read_text():
                        raise RuntimeError("Unhandled exception in server log")
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["passed"] = True
    (output / "network.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
