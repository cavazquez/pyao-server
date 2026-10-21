"""Recorre salidas con WALK/PING TCP, handlers concretos y Redis descartable.

El reloj de cadencia avanza entre casos y las posiciones se preparan como fixture.
No simula el handler ni la transacción; tampoco acredita renderizado o caminos
peatonales entre portales. Los NPC del control de ocupación no ejecutan IA.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import secrets
import shutil
import struct
import subprocess  # noqa: S404 -- Git se ejecuta sin shell y con argumentos fijos.
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import TYPE_CHECKING, Any

from src.config.game_config import RedisConfig
from src.core.schema_manager import ensure_schema_ready
from src.core.server_initializer import ServerInitializer
from src.models.item_catalog import ItemCatalog
from src.models.npc import NPC
from src.network.packet_id import ServerPacketID
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox
from src.operations.two_client_smoke import ProtocolPeer, login_packet, minimum_dependencies
from src.runtime_paths import maps_dir
from src.security.password_executor import close_password_executor, get_password_executor
from src.server import ArgentumServer
from src.services.action_cadence import ActionCadence
from src.services.map.map_resources_service import MapResourcesService
from src.services.map.player_map_service import PlayerMapService
from src.tasks.task_factory import TaskFactory
from src.utils.password_utils import hash_password
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys
from tools.analysis.audit_world_routes import DIRECTIONS, inspect_world

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

Position = tuple[int, int, int]
MAX_SHARDS = 16
BOAT_OBJECT_TYPE = 31
MAX_FIXTURE_BOAT_SKILL = 50
PARTIAL_CONTROL_PAIRS = 10


def git_output(*arguments: str) -> str:
    """Consulta el checkout con el ejecutable Git resuelto, sin shell.

    Returns:
        Salida de Git sin espacios externos.
    """
    git = shutil.which("git")
    require(git is not None, "Git no está disponible para registrar la procedencia")
    assert git is not None  # noqa: S101 -- Estrechamiento de tipo tras require.
    return subprocess.check_output(  # noqa: S603 -- Sólo argumentos Git fijos en este módulo.
        [git, *arguments], cwd=Path(__file__).resolve().parents[2], text=True
    ).strip()


@dataclass(frozen=True)
class Route:
    """Una salida concreta y su destino del inventario versionado."""

    source: Position
    destination: Position

    @classmethod
    def read(cls, row: dict[str, Any]) -> Route:
        """Convierte una fila ya validada por el auditor estático.

        Returns:
            Salida con coordenadas de origen y destino.
        """
        return cls(
            tuple(row[k] for k in ("from_map", "x", "y")),
            tuple(row[k] for k in ("to_map", "to_x", "to_y")),
        )

    def approaches(self, width: int = 100, height: int = 100) -> list[tuple[int, Position]]:
        """Enumera aproximaciones cardinales dentro del mapa de origen.

        Returns:
            Rumbos y posiciones iniciales válidos.
        """
        mid, x, y = self.source
        return [
            (heading, (mid, x - dx, y - dy))
            for heading, dx, dy in DIRECTIONS
            if 1 <= x - dx <= width and 1 <= y - dy <= height
        ]


class Audit:
    """Prepara fixtures aisladas y comprueba los efectos de WALK real."""

    def __init__(self, client: RedisClient, output: Path) -> None:
        """Conecta servicios concretos a la instancia Redis descartable."""
        self.client = client
        self.output = output
        self.deps = minimum_dependencies(client)
        self.maps = self.deps.map_manager
        ServerInitializer._load_map_tiles(self.maps)  # noqa: SLF001 -- Carga real de inicio.
        self.terrain = MapResourcesService(map_manager=self.maps)
        self.deps.map_resources_service = self.terrain
        self.deps.player_map_service = PlayerMapService(
            self.deps.player_repo,
            self.deps.account_repo,
            self.maps,
            self.deps.broadcast_service,
            map_resources=self.terrain,
        )
        self.now = 0.0
        self.deps.action_cadence = ActionCadence(clock=lambda: self.now)
        self.server = ArgentumServer(host="127.0.0.1")
        self.server.deps = self.deps
        self.server.task_factory = TaskFactory(self.deps)
        self.peers: list[ProtocolPeer] = []
        self.users: list[int] = []
        self.senders: list[MessageSender] = []
        self.handling: set[asyncio.Task[None]] = set()
        self.listener: asyncio.Server | None = None
        self.counts: Counter[str] = Counter()
        self.digest = hashlib.sha256()
        self.provenance = {
            "server_commit": git_output("rev-parse", "HEAD"),
            "dirty": bool(git_output("status", "--porcelain")),
            "runtime_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
        catalog = ItemCatalog()
        self.boat = next(
            identity
            for identity in catalog.get_all_item_ids()
            if (data := catalog.get_item_data(identity))
            and data.get("ObjType") == BOAT_OBJECT_TYPE
            and int(str(data.get("MinSkill", 35))) <= MAX_FIXTURE_BOAT_SKILL
        )
        self.started = perf_counter()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Delega cada socket al servidor y conserva sus tareas para cerrarlas."""
        task = asyncio.current_task()
        if task is not None:
            self.handling.add(task)
        try:
            await self.server.handle_client(reader, writer)
        finally:
            if task is not None:
                self.handling.discard(task)

    async def start(self) -> None:
        """Autentica dos usuarios efímeros mediante el protocolo real.

        Raises:
            RuntimeError: El login no registró el emisor del usuario.
        """
        self.listener = await asyncio.start_server(self.handle, "127.0.0.1", 0)
        port = self.listener.sockets[0].getsockname()[1]
        password = secrets.token_urlsafe(24)
        encoded = await get_password_executor().run(hash_password, password)
        for number in (1, 2):
            name = "RouteAudit" + str(number)
            user = await self.deps.account_repo.create_account(
                name,
                encoded,
                "route@example.invalid",
                {"race": 1, "gender": 1, "job": 1, "head": 1, "home": 1},
            )
            self.users.append(user)
            await self.deps.player_repo.set_position(user, 50 + number, 50, 1, 3)
            await self.deps.player_repo.set_stats(
                user,
                max_hp=100,
                min_hp=100,
                max_mana=100,
                min_mana=100,
                max_sta=100,
                min_sta=100,
                gold=0,
                level=20,
                elu=300,
                experience=0,
            )
            await self.deps.player_repo.set_skills(user, navegacion=100, pesca=100)
            await self.deps.inventory_repo.set_slot(user, 1, self.boat, 1)
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            peer = ProtocolPeer(reader, writer)
            self.peers.append(peer)
            await peer.send(login_packet(name, password))
            await peer.wait(
                lambda frames: any(frame[0] == ServerPacketID.LOGGED for frame in frames)
            )
            await self.barrier(peer)
            sender = self.maps.get_player_message_sender(user)
            if sender is None:
                msg = "El login no registró su sender real"
                raise RuntimeError(msg)
            self.senders.append(sender)
        # The second authenticated socket is parked outside the spatial fixture
        # except when its actual player is the destination blocker.
        self.maps.remove_player_from_all_maps(self.users[1])

    @staticmethod
    async def barrier(peer: ProtocolPeer) -> None:
        """Drena respuestas previas usando PING/PONG como barrera de orden."""
        peer.frames.clear()
        await peer.send(b"\x77")
        await peer.wait(lambda frames: any(frame[0] == ServerPacketID.PONG for frame in frames))
        peer.frames.clear()

    async def place(
        self,
        index: int,
        position: Position,
        *,
        boat: bool = True,
        skill: int = 100,
        alive: bool = True,
    ) -> None:
        """Prepara posición, navegación y recursos de un caso independiente."""
        user = self.users[index]
        sender = self.senders[index]
        self.maps.remove_player_from_all_maps(user)
        mid, x, y = position
        water = self.terrain.has_water(mid, x, y)
        async with self.client.redis.pipeline(transaction=False) as pipeline:
            pipeline.hset(
                RedisKeys.player_position(user), mapping={"map": mid, "x": x, "y": y, "heading": 3}
            )
            pipeline.hset(
                RedisKeys.player_user_stats(user),
                mapping={"sailing": int(water), "min_sta": 100, "min_hp": 100 if alive else 0},
            )
            pipeline.hset(RedisKeys.player_skills(user), mapping={"level:navegacion": skill})
            if boat:
                pipeline.hset(RedisKeys.player_inventory(user), "slot_1", f"{self.boat}:1")
            else:
                pipeline.hdel(RedisKeys.player_inventory(user), "slot_1")
            await pipeline.execute()
        self.maps.add_player(mid, user, sender, "RouteAudit" + str(index + 1))
        self.maps.update_player_tile(user, mid, x, y, x, y)

    async def check(  # noqa: PLR0914, PLR0915 -- Preparación, aserciones y limpieza del mismo caso.
        self,
        route: Route,
        heading: int,
        origin: Position,
        label: str,
        *,
        accepted: bool = True,
        boat: bool = True,
        skill: int = 100,
        alive: bool = True,
        blocker: str = "",
    ) -> None:
        """Envía WALK y verifica persistencia, protocolo y ocupación del destino."""
        await self.place(0, origin, boat=boat, skill=skill, alive=alive)
        destination = route.destination
        occupant = None
        npc = None
        if blocker == "player":
            await self.place(1, destination)
            occupant = "player:" + str(self.users[1])
        elif blocker in {"npc-friendly", "npc-hostile"}:
            mid, x, y = destination
            npc = NPC(
                1,
                10001,
                "route-occupant",
                mid,
                x,
                y,
                3,
                "RouteOccupant",
                "synthetic occupancy fixture",
                1,
                1,
                100,
                100,
                1,
                is_hostile=blocker == "npc-hostile",
                is_attackable=True,
            )
            self.maps.add_npc(mid, npc)
            occupant = "npc:" + npc.instance_id
        elif blocker == "reservation":
            mid, x, y = destination
            require(
                self.maps.reserve_arrival(
                    "audit-reservation", mid, x, y, water=self.terrain.has_water(*destination)
                ),
                "No se pudo preparar la reserva",
            )
            occupant = "reservation:audit-reservation"
        elif blocker == "door":
            self.maps.block_tile(*destination)
        peer = self.peers[0]
        peer.frames.clear()
        self.now += 1.0
        try:
            await peer.send(bytes((6, heading, 119)))
            await peer.wait(lambda frames: any(frame[0] == ServerPacketID.PONG for frame in frames))
            user = self.users[0]
            position = await self.deps.player_repo.get_position(user)
            require(position is not None, "Se perdió la posición")
            assert position is not None  # noqa: S101 -- Estrechamiento tras require.
            actual = tuple(position.get(k, 0) for k in ("map", "x", "y"))
            expected = destination if accepted else origin
            require(actual == expected, f"{label}: destino {actual}, esperado {expected}")
            map_frames = [
                struct.unpack_from("<h", frame, 1)[0]
                for frame in peer.frames
                if frame[0] == ServerPacketID.CHANGE_MAP
            ]
            expected_maps = [destination[0]] if accepted and origin[0] != destination[0] else []
            require(map_frames == expected_maps, f"{label}: CHANGE_MAP incoherente")
            positions = [
                (frame[1], frame[2])
                for frame in peer.frames
                if frame[0] == ServerPacketID.POS_UPDATE
            ]
            require(
                bool(positions) and positions[-1] == expected[1:],
                f"{label}: POS_UPDATE incoherente",
            )
            sailing = await self.deps.player_repo.is_sailing(user)
            require(
                sailing == self.terrain.has_water(*expected), f"{label}: navegación incoherente"
            )
            require(
                self.maps.get_tile_occupant(*expected) == f"player:{user}",
                f"{label}: índice espacial incoherente",
            )
            require(
                user in self.maps.get_players_in_map(expected[0]),
                f"{label}: pertenencia al mapa incoherente",
            )
            if occupant:
                require(
                    self.maps.get_tile_occupant(*destination) == occupant,
                    f"{label}: se pisó al ocupante",
                )
            self.counts[label] += 1
            self.counts["total"] += 1
            self.digest.update(
                json.dumps(
                    [route.source, destination, heading, label, actual, sailing],
                    separators=(",", ":"),
                ).encode()
            )
        except BaseException:
            (self.output / "failure.json").write_text(
                json.dumps(
                    {
                        "source": route.source,
                        "destination": destination,
                        "heading": heading,
                        "origin": origin,
                        "label": label,
                        "completed": dict(self.counts),
                    },
                    indent=2,
                )
                + "\n"
            )
            raise
        finally:
            peer.frames.clear()
            if blocker == "player":
                self.maps.remove_player_from_all_maps(self.users[1])
            elif npc:
                self.maps.remove_npc(npc.map_id, npc.instance_id)
            elif blocker == "reservation":
                self.maps.release_positions("audit-reservation", destination)
            elif blocker == "door":
                self.maps.unblock_tile(*destination)
            if self.counts["total"] % 1000 == 0:
                await self.barrier(self.peers[1])
                progress = {
                    "counts": dict(self.counts),
                    "seconds": round(perf_counter() - self.started, 2),
                }
                (self.output / "progress.json").write_text(json.dumps(progress, indent=2) + "\n")
                print(json.dumps(progress), flush=True)

    async def run(
        self, routes: list[Route], *, limit: int, shard: int, shards: int
    ) -> dict[str, Any]:
        """Recorre las entradas y controles asignados a esta partición.

        Returns:
            Conteos esperados y alcance seleccionado.
        """
        await self.start()
        representatives: dict[tuple[int, int], Route] = {}
        for route in routes:
            representatives.setdefault((route.source[0], route.destination[0]), route)
        for number, route in enumerate(routes):
            if limit and self.counts["all-exit-directions"] >= limit:
                break
            if number % shards != shard:
                continue
            for heading, origin in route.approaches(*self.maps.get_map_size(route.source[0])):
                await self.check(route, heading, origin, "all-exit-directions")
                if limit and self.counts["all-exit-directions"] >= limit:
                    break
        for number, route in enumerate(representatives.values()):
            if limit and number >= PARTIAL_CONTROL_PAIRS:
                break
            if number % shards != shard:
                continue
            heading, origin = route.approaches(*self.maps.get_map_size(route.source[0]))[0]
            for blocker in ("player", "npc-friendly", "npc-hostile", "reservation", "door"):
                await self.check(route, heading, origin, blocker, accepted=False, blocker=blocker)
            water = self.terrain.has_water(*route.destination)
            for label, boat, skill, alive in (
                ("no-boat", False, 100, True),
                ("insufficient-navigation", True, 0, True),
                ("dead", True, 100, False),
            ):
                await self.check(
                    route,
                    heading,
                    origin,
                    label,
                    accepted=not water,
                    boat=boat,
                    skill=skill,
                    alive=alive,
                )
            for label, bad in (
                ("missing-map", (999, 50, 50)),
                ("x-zero", (route.destination[0], 0, 50)),
                ("x-over", (route.destination[0], 101, 50)),
                ("y-zero", (route.destination[0], 50, 0)),
                ("y-over", (route.destination[0], 50, 101)),
            ):
                original = self.maps._exit_tiles[route.source]  # noqa: SLF001 -- Fixture inválida.
                self.maps._exit_tiles[route.source] = dict(  # noqa: SLF001
                    zip(("to_map", "to_x", "to_y"), bad, strict=True)
                )
                try:
                    await self.check(
                        Route(route.source, bad), heading, origin, label, accepted=False
                    )
                finally:
                    self.maps._exit_tiles[route.source] = original  # noqa: SLF001
        selected_routes = [route for i, route in enumerate(routes) if i % shards == shard]
        selected_pairs = [pair for i, pair in enumerate(representatives) if i % shards == shard]
        expected_inputs = sum(
            len(route.approaches(*self.maps.get_map_size(route.source[0])))
            for route in selected_routes
        )
        if not limit:
            require(
                self.counts["all-exit-directions"] == expected_inputs, "Faltan entradas cardinales"
            )
            require(
                all(
                    self.counts[label] == len(selected_pairs)
                    for label in (
                        "player",
                        "npc-friendly",
                        "npc-hostile",
                        "reservation",
                        "door",
                        "no-boat",
                        "insufficient-navigation",
                        "dead",
                        "missing-map",
                        "x-zero",
                        "x-over",
                        "y-zero",
                        "y-over",
                    )
                ),
                "Faltan controles de pares dirigidos",
            )
        return {
            "partial": bool(limit),
            "directed_pairs_in_inventory": len(representatives),
            "exit_tiles_selected": len(selected_routes),
            "directed_pairs_selected": selected_pairs,
            "expected_cardinal_inputs": expected_inputs,
        }

    async def close(self) -> None:
        """Cierra ambos sockets, el listener y las tareas de conexión."""
        await asyncio.gather(*(peer.close() for peer in self.peers), return_exceptions=True)
        if self.listener:
            self.listener.close()
            await self.listener.wait_closed()
        if self.handling:
            async with asyncio.timeout(10):
                await asyncio.gather(*self.handling)


async def scenario(
    settings: RedisConfig,
    output: Path,
    *,
    limit: int,
    shard: int,
    shards: int,
    source: Position | None = None,
) -> dict[str, Any]:
    """Ejecuta una partición y guarda su evidencia y procedencia.

    Returns:
        Evidencia del recorrido completado.

    Raises:
        ValueError: La reproducción no identifica una salida única.
    """
    client = RedisClient()
    await client.connect(settings, seed_defaults=False)
    audit = None
    try:
        await ensure_schema_ready(client.redis)
        await client.initialize_defaults()
        report, rows, _ = inspect_world(maps_dir())
        routes = [Route.read(row) for row in rows]
        if source is not None:
            routes = [route for route in routes if route.source == source]
            if len(routes) != 1:
                msg = "La coordenada no identifica una salida única"
                raise ValueError(msg)
        audit = Audit(client, output)
        coverage = await audit.run(routes, limit=limit, shard=shard, shards=shards)
        if source is not None:
            coverage["partial"] = True
            coverage["selected_source"] = source
        result = {
            "passed": True,
            **coverage,
            **audit.provenance,
            "network_crossings": True,
            "transport": "TCP loopback with actual framing and authentication",
            "redis": "disposable authenticated instance",
            "counts": dict(audit.counts),
            "results_sha256": audit.digest.hexdigest(),
            "inventory_summary": report["summary"],
            "source_hashes": report["sources"],
            "shard": shard,
            "shards": shards,
            "seconds": round(perf_counter() - audit.started, 2),
            "controlled_clock": "cadence advances one second between independent fixture cases",
            "rendering_tested": False,
            "npc_ai_tested": False,
            "between_portals_pathfinding_tested": False,
        }
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        try:
            if audit:
                await audit.close()
        finally:
            try:
                await close_password_executor()
            finally:
                await client.disconnect()


def combine(paths: list[Path], output: Path) -> dict[str, Any]:
    """Exige una unión completa, limpia y coherente de todas las particiones.

    Returns:
        Evidencia conjunta de cobertura completa.

    Raises:
        ValueError: Faltan particiones o sus identidades y conteos no coinciden.
    """
    records = [json.loads(path.read_text()) for path in paths]
    if not records or any(
        row.get("passed") is not True
        or row.get("partial") is not False
        or row.get("dirty") is not False
        for row in records
    ):
        msg = "Se requieren particiones completas, aprobadas y limpias"
        raise ValueError(msg)
    first = records[0]
    shards = first["shards"]
    if len(records) != shards or {row["shard"] for row in records} != set(range(shards)):
        msg = "Faltan particiones o están repetidas"
        raise ValueError(msg)
    commit = git_output("rev-parse", "HEAD")
    script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for row in records:
        if (
            row["server_commit"] != commit
            or row["runtime_source_sha256"] != script
            or any(
                row[key] != first[key] for key in ("shards", "source_hashes", "inventory_summary")
            )
        ):
            msg = "Particiones de otro código o dataset"
            raise ValueError(msg)
    counts: Counter[str] = Counter()
    pairs: list[tuple[int, int]] = []
    for row in records:
        counts.update(row["counts"])
        pairs.extend(tuple(pair) for pair in row["directed_pairs_selected"])
    inventory = first["inventory_summary"]
    if (
        counts["all-exit-directions"] != inventory["cardinal_inputs"]
        or sum(row["exit_tiles_selected"] for row in records) != inventory["exit_tiles"]
        or len(pairs) != len(set(pairs))
        or len(pairs) != inventory["directed_pairs"]
    ):
        msg = "La unión no cubre todas las salidas, direcciones y pares"
        raise ValueError(msg)
    labels = {
        "player",
        "npc-friendly",
        "npc-hostile",
        "reservation",
        "door",
        "no-boat",
        "insufficient-navigation",
        "dead",
        "missing-map",
        "x-zero",
        "x-over",
        "y-zero",
        "y-over",
    }
    if any(counts[label] != len(pairs) for label in labels) or counts["total"] != counts[
        "all-exit-directions"
    ] + len(labels) * len(pairs):
        msg = "Faltan controles de navegación, ocupación o límites"
        raise ValueError(msg)
    result = {
        key: first[key]
        for key in ("server_commit", "runtime_source_sha256", "source_hashes", "inventory_summary")
    }
    result.update(
        passed=True,
        partial=False,
        dirty=False,
        full_coverage=True,
        network_crossings=True,
        counts=dict(counts),
        shards=shards,
        evidence_sha256={
            path.parent.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
        },
        rendering_tested=False,
        npc_ai_tested=False,
        between_portals_pathfinding_tested=False,
    )
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    """Ejecuta la auditoría completa, una reproducción o la unión de recibos."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--combine",
        type=Path,
        nargs="+",
        help="Verifica la unión de todas las particiones sin iniciar Redis",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Smoke parcial; cero recorre todas las entradas"
    )
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument(
        "--route",
        type=int,
        nargs=3,
        metavar=("MAP", "X", "Y"),
        help="Reproduce una salida concreta; el resultado queda marcado como parcial",
    )
    args = parser.parse_args()
    if args.limit < 0 or not 0 <= args.shard < args.shards <= MAX_SHARDS:
        parser.error("Límite o partición inválidos")
    if args.route and args.shards != 1:
        parser.error("La reproducción puntual requiere una sola partición")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if args.combine:
        print(json.dumps(combine(args.combine, output), indent=2))
        return
    logging.basicConfig(level=logging.ERROR)
    with (
        TemporaryDirectory(prefix="pyao-route-state-") as temporary,
        RedisSandbox(appendonly=False) as sandbox,
    ):
        os.environ["PYAO_STATE_DIR"] = temporary
        settings = RedisConfig(
            host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file
        )
        print(
            json.dumps(
                asyncio.run(
                    scenario(
                        settings,
                        output,
                        limit=args.limit,
                        shard=args.shard,
                        shards=args.shards,
                        source=(args.route[0], args.route[1], args.route[2])
                        if args.route
                        else None,
                    )
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
