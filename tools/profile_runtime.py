"""Run the ordinary server with bounded latency diagnostics, without payloads.

python -m tools.profile_runtime --output /tmp/runtime.json -- --host 127.0.0.1 ...
Only command names, packet classes, elapsed times and counters are retained.
The ordinary server entry point does not import or enable this diagnostic.
"""

import argparse
import asyncio
import atexit
from collections import Counter, deque
from contextvars import ContextVar
from functools import wraps
import json
from pathlib import Path
import sys
import time

_packet = ContextVar("profile_packet", default="background")
COMMANDS = {"GET", "SET", "HGET", "HGETALL", "HSET", "HMGET", "EXISTS", "WATCH", "UNWATCH", "EXEC", "MULTI", "EVAL", "EVALSHA", "SCAN", "KEYS", "SMEMBERS", "SADD", "SREM", "WAITAOF", "DEL", "EXPIRE", "PING", "INCR", "DECR"}


class RuntimeProfile:
    def __init__(self, limit=4096, threshold_ms=5.0):
        self.events = deque(maxlen=limit)
        self.counts = Counter()
        self.maximum_ms = {}
        self.threshold_ms = threshold_ms
        self.event_count = 0

    def record(self, stage, started, elapsed_ms=None):
        elapsed = (time.monotonic() - started) * 1000 if elapsed_ms is None else elapsed_ms
        self.counts[stage] += 1
        self.maximum_ms[stage] = max(elapsed, self.maximum_ms.get(stage, 0))
        if elapsed >= self.threshold_ms:
            self.event_count += 1
            self.events.append({"stage": stage, "packet": _packet.get(), "started_monotonic": started, "elapsed_ms": elapsed})

    def wrap(self, method, stage, *, command=False):
        @wraps(method)
        async def measured(*args, **kwargs):
            label = stage
            if command:
                # A strict allowlist prevents arguments/keys becoming labels.
                name = args[1] if len(args) > 1 else "other"
                label += ":" + (name if isinstance(name, str) and name in COMMANDS else "other")
            started = time.monotonic()
            try:
                return await method(*args, **kwargs)
            finally:
                self.record(label, started)
        return measured

    def report(self):
        return {"counts": dict(self.counts), "maximum_ms": self.maximum_ms, "events": list(self.events), "event_limit": self.events.maxlen, "dropped_events": self.event_count - len(self.events), "threshold_ms": self.threshold_ms, "contains_payloads": False}


def install(profile):
    from redis.asyncio.client import Redis, Pipeline
    from src.server import ArgentumServer
    from src.utils import durability
    from src.security.password_executor import PasswordExecutor
    from src.services.map.player_map_service import PlayerMapService
    from src.services.map.map_transition_steps import ClientLoadDelayStep
    from src.command_handlers.login_spawn_handler import LoginSpawnHandler

    Redis.execute_command = profile.wrap(Redis.execute_command, "redis", command=True)
    Pipeline.immediate_execute_command = profile.wrap(Pipeline.immediate_execute_command, "redis-watch", command=True)
    Pipeline.execute = profile.wrap(Pipeline.execute, "redis-pipeline")
    PasswordExecutor.run = profile.wrap(PasswordExecutor.run, "password-executor")
    for cls, names in (
        (PlayerMapService, ("_send_players_in_map", "_send_npcs_in_map", "_send_ground_items_in_map", "_unblock_exit_tiles")),
        (ClientLoadDelayStep, ("execute",)),
        (LoginSpawnHandler, ("spawn_player", "send_map_data")),
    ):
        for name in names:
            setattr(cls, name, profile.wrap(getattr(cls, name), cls.__name__ + "." + name))
    original = durability.require_durable
    measured = profile.wrap(original, "aof-barrier")
    # Some service modules have already imported the function during Server import.
    for name, module in tuple(sys.modules.items()):
        if name.startswith("src.") and getattr(module, "require_durable", None) is original:
            module.require_durable = measured
    asyncio.StreamWriter.drain = profile.wrap(asyncio.StreamWriter.drain, "writer-drain")
    create_task = ArgentumServer.create_task

    def traced_task(*args, **kwargs):
        task = create_task(*args, **kwargs)
        execute = task.execute
        label = type(task).__name__

        async def traced_execute():
            token = _packet.set(label)
            started = time.monotonic()
            try:
                return await execute()
            finally:
                profile.record("packet:" + label, started)
                _packet.reset(token)
        task.execute = traced_execute
        return task
    ArgentumServer.create_task = traced_task
    run = asyncio.run

    async def monitor():
        while True:
            started = time.monotonic()
            await asyncio.sleep(0.02)
            profile.record("event-loop-lag", started + 0.02)

    async def instrumented(coroutine):
        observer = asyncio.create_task(monitor(), name="runtime-profile-loop-lag")
        try:
            return await coroutine
        finally:
            observer.cancel()
            await asyncio.gather(observer, return_exceptions=True)

    asyncio.run = lambda coroutine, **kwargs: run(instrumented(coroutine), **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("server_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile = RuntimeProfile()
    atexit.register(lambda: args.output.write_text(json.dumps(profile.report(), indent=2) + "\n"))
    install(profile)
    from src.run_server import main as server_main
    sys.argv = ["pyao-server", *args.server_args[1:]] if args.server_args[:1] == ["--"] else ["pyao-server", *args.server_args]
    server_main()


if __name__ == "__main__":
    main()
