#!/usr/bin/env python3
"""Carga real sobre un servidor aislado. Ejecutar con uv run python tools/benchmark.py.

Las cuentas deben pertenecer exclusivamente al ensayo. El valor predeterminado
apunta a loopback y nunca descubre un endpoint de producción. El informe no guarda
contraseñas ni bytes de login. El servidor expone ticks con PYAO_METRICS_FILE.
"""

import argparse
import asyncio
from collections import Counter, deque
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import platform
import ssl
import struct
import time

from src import __version__
from src.network.packet_framer import packet_length
from src.network.packet_id import ClientPacketID, ServerPacketID
from src.operations.two_client_smoke import login_packet
from src.utils.gold_atomic import operation_id


def percentile(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, max(0, math.ceil(len(values) * p) - 1))] if values else None


class Peer:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.counts = Counter()
        self.ready = asyncio.Event()
        self.pong = None
        self.error = None
        self.actions = {}
        self.attack_samples = deque(maxlen=10000)
        self.accepted_samples = deque(maxlen=10000)
        self.damage_samples = deque(maxlen=10000)
        self.rejected = 0
        self.user_id = 0
        self.tracked_actions = {}
        self.receiver = asyncio.create_task(self.receive())

    async def receive(self):
        pending = b""
        try:
            while chunk := await self.reader.read(4096):
                pending += chunk
                while (length := packet_length(pending, "server")) is not None:
                    frame, pending = pending[:length], pending[length:]
                    self.counts[frame[0]] += 1
                    if frame[0] == ServerPacketID.UPDATE_USER_STATS:
                        self.ready.set()
                    if frame[0] == ServerPacketID.SKILL_ACTION_STATE:
                        reply = json.loads(frame[4:])
                        future = self.actions.pop(reply["id"], None)
                        if future and not future.done():
                            future.set_result((time.perf_counter(), reply))
                    if frame[0] == ServerPacketID.VISUAL_DAMAGE:
                        size = int.from_bytes(frame[1:3], "little")
                        event = frame[3 : 3 + size].decode("ascii")
                        actor = struct.unpack_from("<i", frame, 3 + size + 2)[0]
                        amount = struct.unpack_from("<i", frame, 3 + size + 8)[0]
                        sent = self.tracked_actions.get(event.split(":")[0])
                        if actor == self.user_id and amount > 0 and sent is not None:
                            self.damage_samples.append((time.perf_counter() - sent) * 1000)
                    if frame[0] == ServerPacketID.PONG and self.pong and not self.pong.done():
                        self.pong.set_result(time.perf_counter())
                if len(pending) > 4096:
                    raise RuntimeError("Buffer de respuesta excedido")
            raise ConnectionError("Conexión cerrada durante carga")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.error = type(error).__name__
            self.ready.set()
            if self.pong and not self.pong.done():
                self.pong.set_exception(ConnectionError(self.error))

    async def close(self):
        self.receiver.cancel()
        self.writer.close()
        await asyncio.gather(self.receiver, self.writer.wait_closed(), return_exceptions=True)


async def benchmark(args):
    profiles = json.loads(args.accounts.read_text())
    if len(profiles) < args.connections + args.slow_readers:
        raise ValueError("Faltan cuentas únicas del fixture")
    context = ssl.create_default_context(cafile=str(args.ca)) if args.ca else None
    tracked_actions = {}
    peers = []
    slow = []
    latencies = deque(maxlen=100000)
    logins = []
    first_stats = []
    errors = []
    outliers = deque(maxlen=1000)
    ticks_before = (
        json.loads(args.metrics.read_text()) if args.metrics and args.metrics.exists() else None
    )
    samples = []

    def proc_sample():
        if not args.pid:
            return {}
        try:
            stat = Path(f"/proc/{args.pid}/stat").read_text().rsplit(")", 1)[1].split()
            return {
                "time": time.monotonic(),
                "cpu_seconds": (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK"),
                "rss_bytes": int(stat[21]) * os.sysconf("SC_PAGE_SIZE"),
            }
        except OSError, ValueError, IndexError:
            return {}

    try:
        for profile in profiles[: args.connections]:
            start = time.perf_counter()
            reader, writer = await asyncio.open_connection(
                args.host,
                args.port,
                ssl=context,
                server_hostname=args.tls_name if context else None,
            )
            peer = Peer(reader, writer)
            peer.user_id = profile.get("user_id", 0)
            peer.tracked_actions = tracked_actions
            peers.append(peer)
            writer.write(login_packet(profile["username"], profile["password"]))
            await writer.drain()
            await asyncio.wait_for(peer.ready.wait(), 10)
            if peer.error:
                raise ConnectionError(peer.error)
            first_stats.append((time.perf_counter() - start) * 1000)
            # UPDATE_USER_STATS llega antes del spawn. Un PONG detrás del LOGIN
            # confirma que el handler completo terminó, sin ocultar esa espera
            # dentro de la primera muestra de latencia durante el juego.
            peer.pong = asyncio.get_running_loop().create_future()
            writer.write(bytes([ClientPacketID.PING]))
            await writer.drain()
            await asyncio.wait_for(peer.pong, 5)
            logins.append((time.perf_counter() - start) * 1000)
            if getattr(args, "combat_receipts", False):
                peer.pong = asyncio.get_running_loop().create_future()
                writer.write(struct.pack("<BBiB", 250, 1, 272, ClientPacketID.PING))
                await writer.drain()
                await asyncio.wait_for(peer.pong, 5)
        for profile in profiles[args.connections : args.connections + args.slow_readers]:
            reader, writer = await asyncio.open_connection(
                args.host,
                args.port,
                ssl=context,
                server_hostname=args.tls_name if context else None,
            )
            writer.write(login_packet(profile["username"], profile["password"]))
            await writer.drain()
            slow.append((reader, writer))
        started = time.monotonic()
        deadline = started + args.seconds

        async def exercise(index, peer):
            iteration = 0
            while time.monotonic() < deadline:
                try:
                    peer.pong = asyncio.get_running_loop().create_future()
                    before = time.perf_counter()
                    peer.writer.write(bytes([ClientPacketID.PING]))
                    # Un cuadrado pequeño, cadencia menor que el máximo del servidor.
                    if getattr(args, "combat", False):
                        if getattr(args, "combat_receipts", False):
                            identity = operation_id()
                            tracked_actions[identity] = time.perf_counter()
                            if len(tracked_actions) > 4096:
                                tracked_actions.pop(next(iter(tracked_actions)))
                            acknowledgment = asyncio.get_running_loop().create_future()
                            peer.actions[identity] = acknowledgment
                            request = json.dumps(
                                {
                                    "id": identity,
                                    "action": "attack",
                                    "params": {"x": 20 + (index ^ 1), "y": 64},
                                },
                                separators=(",", ":"),
                            ).encode("ascii")
                            peer.writer.write(struct.pack("<BBH", 251, 1, len(request)) + request)
                        else:
                            peer.writer.write(bytes([ClientPacketID.ATTACK]))
                    else:
                        peer.writer.write(bytes([ClientPacketID.WALK, (2, 3, 4, 1)[iteration % 4]]))
                    if iteration % 12 == 0:
                        text = f"Ensayo {index} {iteration}".encode("ascii")
                        peer.writer.write(
                            bytes([ClientPacketID.TALK]) + struct.pack("<H", len(text)) + text
                        )
                    await peer.writer.drain()
                    end = await asyncio.wait_for(peer.pong, 5)
                    elapsed = (end - before) * 1000
                    latencies.append(elapsed)
                    if elapsed >= 10:
                        outliers.append(
                            {
                                "peer": index,
                                "iteration": iteration,
                                "started_monotonic": before,
                                "elapsed_ms": elapsed,
                            }
                        )
                    if getattr(args, "combat_receipts", False):
                        acknowledged, reply = await asyncio.wait_for(acknowledgment, 5)
                        elapsed_ack = (acknowledged - tracked_actions[identity]) * 1000
                        peer.attack_samples.append(elapsed_ack)
                        if reply.get("applied"):
                            peer.accepted_samples.append(elapsed_ack)
                        else:
                            peer.rejected += 1
                    iteration += 1
                    await asyncio.sleep(args.cadence)
                except (TimeoutError, ConnectionError, OSError) as error:
                    errors.append(type(error).__name__)
                    return

        async def measure():
            while time.monotonic() < deadline:
                sample = proc_sample()
                if sample:
                    samples.append(sample)
                await asyncio.sleep(0.5)

        # Los lectores lentos no consumen respuestas; una ráfaga acotada prueba aislamiento.
        for _, writer in slow:
            writer.write(bytes([ClientPacketID.PING]) * 300)
            try:
                await writer.drain()
            except ConnectionError:
                pass
        await asyncio.gather(*(exercise(i, p) for i, p in enumerate(peers)), measure())
        ticks_after = (
            json.loads(args.metrics.read_text()) if args.metrics and args.metrics.exists() else None
        )
        metrics = {
            "version": __version__,
            "started_at": datetime.now(UTC).isoformat(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
            "connections": len(peers),
            "slow_readers": len(slow),
            "seconds": time.monotonic() - started,
            "login_ms": {
                "p50": percentile(logins, 0.5),
                "p95": percentile(logins, 0.95),
                "max": max(logins, default=None),
            },
            "rtt_ms": {
                "samples": len(latencies),
                "sample_limit": 100000,
                "p50": percentile(latencies, 0.5),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
                "max": max(latencies, default=None),
            },
            "errors": errors,
            "packets": dict(sum((p.counts for p in peers), Counter())),
            "server_process": samples,
            "tick_before": ticks_before,
            "tick_after": ticks_after,
            "budgets": {"rtt_p95_ms": args.max_p95_ms, "login_ms": args.max_login_ms},
            "passed": bool(latencies)
            and not errors
            and (args.max_p95_ms is None or percentile(latencies, 0.95) <= args.max_p95_ms)
            and (args.max_login_ms is None or max(logins) <= args.max_login_ms),
        }

        def latency_summary(values):
            return {
                "samples": len(values),
                "p50": percentile(values, 0.5),
                "p95": percentile(values, 0.95),
                "p99": percentile(values, 0.99),
                "max": max(values, default=None),
            }

        metrics["attack_ack_ms"] = latency_summary(
            [v for peer in peers for v in peer.attack_samples]
        )
        metrics["accepted_attack_ack_ms"] = latency_summary(
            [v for peer in peers for v in peer.accepted_samples]
        )
        metrics["target_damage_visibility_ms"] = latency_summary(
            [v for peer in peers for v in peer.damage_samples]
        )
        metrics["cadence_rejections"] = sum(peer.rejected for peer in peers)
        metrics["combat_receipts"] = getattr(args, "combat_receipts", False)
        metrics["workload"] = "physical_combat" if getattr(args, "combat", False) else "movement"
        metrics["outliers_ms"] = list(outliers)
        metrics["started_monotonic"] = started
        metrics["login_first_stats_ms"] = {
            "p50": percentile(first_stats, 0.5),
            "p95": percentile(first_stats, 0.95),
            "max": max(first_stats, default=None),
        }
        metrics["login_readiness"] = (
            "PONG ordered after the complete LOGIN handler; first stats are reported separately"
        )
        args.output.write_text(json.dumps(metrics, indent=2) + "\n")
        return metrics
    finally:
        await asyncio.gather(*(p.close() for p in peers), return_exceptions=True)
        for _, writer in slow:
            writer.close()
            await asyncio.gather(writer.wait_closed(), return_exceptions=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=17666)
    p.add_argument("--allow-remote", action="store_true")
    p.add_argument("--accounts", type=Path, required=True)
    p.add_argument("--connections", type=int, default=2)
    p.add_argument("--slow-readers", type=int, default=0)
    p.add_argument("--seconds", type=int, default=60)
    p.add_argument("--cadence", type=float, default=0.35)
    p.add_argument("--pid", type=int)
    p.add_argument("--metrics", type=Path)
    p.add_argument("--ca", type=Path)
    p.add_argument("--tls-name", default="localhost")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-p95-ms", type=float)
    p.add_argument("--max-login-ms", type=float)
    p.add_argument("--combat", action="store_true")
    p.add_argument("--combat-receipts", action="store_true")
    a = p.parse_args()
    if a.host not in {"127.0.0.1", "localhost", "::1"} and not a.allow_remote:
        p.error("Usar loopback o autorizar explícitamente --allow-remote para un entorno de ensayo")
    if (
        not 1 <= a.connections <= 500
        or not 0 <= a.slow_readers <= 10
        or not 1 <= a.seconds <= 3600
        or a.cadence < 0.05
    ):
        p.error("Carga o duración fuera de límites")
    report = asyncio.run(benchmark(a))
    print(
        json.dumps(
            {"passed": report["passed"], "connections": a.connections, "rtt_ms": report["rtt_ms"]}
        )
    )
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
