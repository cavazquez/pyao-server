"""Smoke de dos clientes TCP reales, handlers reales y Redis descartable autenticado.

La fixture usa un mapa vacío y repositorios/servicios concretos. No inicia NPCs ni
el tick periódico: valida el recorrido de red, autenticación, sesiones y movimiento,
no la aceptación completa del juego ni la prueba Godot de 30 minutos.
"""

import asyncio
import json
import logging
import struct
from collections.abc import Callable
from dataclasses import MISSING, fields
from typing import TYPE_CHECKING, Any

from src.config.game_config import RedisConfig
from src.core.dependency_container import DependencyContainer
from src.core.repository_initializer import RepositoryInitializer
from src.core.schema_manager import ensure_schema_ready
from src.game.map_manager import MapManager
from src.models.spell_catalog import SpellCatalog
from src.network.packet_framer import CONTRACT, FramingError, packet_length
from src.network.packet_id import ServerPacketID
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox
from src.security.password_executor import close_password_executor, get_password_executor
from src.server import ArgentumServer
from src.services.action_cadence import ActionCadence
from src.services.map.player_map_service import PlayerMapService
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.services.player.stamina_service import StaminaService
from src.tasks.task_factory import TaskFactory
from src.utils.password_utils import hash_password
from src.utils.redis_client import RedisClient

if TYPE_CHECKING:
    from src.repositories.player_repository import PlayerRepository

SMOKE_TIMEOUT_SECONDS = 8
GOLD_OFFSET = 13
A_START = 50
B_START = 60
LAST_SLOT = int(CONTRACT["inventory_slots"])
SECOND_PONG = 2


class ProtocolPeer:
    """Cliente real con reconstrucción de respuestas y espera acotada por condición."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Conserva streams, paquetes recibidos y un receptor propio."""
        self.reader = reader
        self.writer = writer
        self.frames: list[bytes] = []
        self.condition = asyncio.Condition()
        self.error: Exception | None = None
        self.eof = False
        self.task = asyncio.create_task(self._receive())

    async def _receive(self) -> None:
        """Reconstruye mensajes del servidor sin asumir fronteras de TCP."""
        pending = b""
        try:
            while chunk := await self.reader.read(1024):
                pending += chunk
                while (length := packet_length(pending, "server")) is not None:
                    frame, pending = pending[:length], pending[length:]
                    async with self.condition:
                        self.frames.append(frame)
                        self.condition.notify_all()
            require(not pending, "EOF del cliente con paquete incompleto")
        except (ConnectionError, FramingError, RuntimeError) as error:
            self.error = error
        finally:
            self.eof = True
            async with self.condition:
                self.condition.notify_all()

    async def wait(self, predicate: Callable[[list[bytes]], bool]) -> None:
        """Espera una condición observable o informa EOF/error con plazo fijo.

        Raises:
            RuntimeError: Ante EOF o un error del receptor antes de cumplir la condición.
        """
        async with asyncio.timeout(SMOKE_TIMEOUT_SECONDS), self.condition:
            await self.condition.wait_for(lambda: predicate(self.frames) or self.eof)
            if self.error is not None:
                msg = f"Falló el receptor de prueba: {type(self.error).__name__}"
                raise RuntimeError(msg) from self.error
            require(predicate(self.frames), "EOF antes de completar el escenario")

    async def send(self, data: bytes) -> None:
        """Envía bytes al transporte real sin registrar su contenido."""
        self.writer.write(data)
        await self.writer.drain()

    async def close(self) -> None:
        """Cierra el transporte y espera el receptor sin dejar tareas huérfanas."""
        self.writer.close()
        await self.writer.wait_closed()
        async with asyncio.timeout(SMOKE_TIMEOUT_SECONDS):
            await self.task


def login_packet(username: str, password: str) -> bytes:
    """Construye el mismo layout de las fixtures compartidas de login.

    Returns:
        ID 0, dos cadenas u16/Latin-1 y tripleta de versión legacy.
    """
    data = b"\x00"
    for value in (username, password):
        encoded = value.encode("latin-1")
        data += struct.pack("<H", len(encoded)) + encoded
    return data + b"\x00\x0d\x00"


def minimum_dependencies(client: RedisClient) -> DependencyContainer:
    """Construye dependencias concretas para el mapa mínimo de la fixture.

    Returns:
        Contenedor con autenticación, persistencia, spawn, broadcast y movimiento reales.
    """
    repositories = RepositoryInitializer(client).initialize_all()
    player = repositories["player_repo"]
    account = repositories["account_repo"]
    maps = MapManager(repositories["ground_items_repo"])
    broadcast = MultiplayerBroadcastService(maps, player, account)
    values: dict[str, Any] = {
        entry.name: None
        for entry in fields(DependencyContainer)
        if entry.default is MISSING and entry.default_factory is MISSING
    }
    values.update(repositories)
    values.update(
        redis_client=client,
        map_manager=maps,
        broadcast_service=broadcast,
        player_map_service=PlayerMapService(player, account, maps, broadcast),
        stamina_service=StaminaService(player),
        spell_catalog=SpellCatalog(),
    )
    return DependencyContainer(**values)


async def position_of(repository: PlayerRepository, user_id: int) -> dict[str, int]:
    """Lee una posición requerida por la fixture.

    Returns:
        Posición completa del personaje.

    Raises:
        RuntimeError: Si una sesión perdió su posición persistida.
    """
    position = await repository.get_position(user_id)
    if position is None:
        msg = "El personaje de prueba perdió su posición"
        raise RuntimeError(msg)
    return position


async def verify_own_session(peer: ProtocolPeer, job: int, gold: int, user_id: int) -> None:
    """Comprueba clase, índice y estadísticas exclusivas de una conexión."""

    def received_own_stats(frames: list[bytes]) -> bool:
        return any(
            frame[0] == ServerPacketID.UPDATE_USER_STATS
            and struct.unpack_from("<i", frame, GOLD_OFFSET)[0] == gold
            for frame in frames
        )

    await peer.wait(received_own_stats)
    await peer.wait(
        lambda frames: any(
            frame[0] == ServerPacketID.CHANGE_INVENTORY_SLOT and frame[1] == LAST_SLOT
            for frame in frames
        )
    )
    require(
        [frame[1] for frame in peer.frames if frame[0] == ServerPacketID.LOGGED] == [job],
        "Logged pertenece exclusivamente a su cuenta",
    )
    require(
        [
            struct.unpack_from("<h", frame, 1)[0]
            for frame in peer.frames
            if frame[0] == ServerPacketID.USER_CHAR_INDEX_IN_SERVER
        ]
        == [user_id],
        "índice propio de cada sesión",
    )
    require(
        [
            struct.unpack_from("<i", frame, GOLD_OFFSET)[0]
            for frame in peer.frames
            if frame[0] == ServerPacketID.UPDATE_USER_STATS
        ]
        == [gold],
        "estadísticas propias sin cruce de sesiones",
    )


async def scenario(settings: RedisConfig) -> dict[str, Any]:  # noqa: PLR0914, PLR0915 - escenario secuencial de integración
    """Comprueba login aislado, framing, movimiento y desconexión de A con B activo.

    Returns:
        Evidencia de comportamiento sin credenciales ni payloads.
    """
    client = RedisClient()
    peers: list[ProtocolPeer] = []
    handling: set[asyncio.Task[None]] = set()
    one_left = asyncio.Event()
    listener: asyncio.Server | None = None
    server: ArgentumServer | None = None
    await client.connect(settings, seed_defaults=False)
    try:
        await ensure_schema_ready(client.redis)
        await client.initialize_defaults()
        deps = minimum_dependencies(client)
        deps.action_cadence = ActionCadence(clock=lambda: 0.0)
        server = ArgentumServer(host="127.0.0.1")
        server.deps = deps
        server.task_factory = TaskFactory(deps)
        profiles = [
            ("SmokePeñaA", "Synthetic-Smoke-A1", 1, 111, 50),
            ("SmokeB", "Synthetic-Smoke-B2", 3, 222, 60),
        ]
        user_ids = []
        for username, password, job, gold, coordinate in profiles:
            password_hash = await get_password_executor().run(hash_password, password)
            uid = await deps.account_repo.create_account(
                username,
                password_hash,
                "smoke@example.invalid",
                {"race": 1, "gender": 1, "job": job, "head": 1, "home": 1},
            )
            user_ids.append(uid)
            await deps.player_repo.set_position(uid, coordinate, coordinate, 1, 3)
            await deps.player_repo.set_attributes(
                uid, strength=10, agility=10, intelligence=10, charisma=10, constitution=10
            )
            await deps.player_repo.set_stats(
                uid,
                max_hp=100,
                min_hp=100,
                max_mana=100,
                min_mana=100,
                max_sta=100,
                min_sta=100,
                gold=gold,
                level=1,
                elu=300,
                experience=0,
            )
            await deps.player_repo.set_skills(uid, magia=10)
            await deps.inventory_repo.set_slot(uid, 30, 1, 2)

        async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            task = asyncio.current_task()
            if task is not None:
                handling.add(task)
            try:
                await server.handle_client(reader, writer)
            finally:
                if task is not None:
                    handling.discard(task)
                    if len(handling) == 1:
                        one_left.set()

        listener = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = listener.sockets[0].getsockname()[1]
        for _ in profiles:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            peers.append(ProtocolPeer(reader, writer))
        await asyncio.gather(
            *(
                peer.send(login_packet(profile[0], profile[1]))
                for peer, profile in zip(peers, profiles, strict=True)
            )
        )
        for peer, profile, uid in zip(peers, profiles, user_ids, strict=True):
            await verify_own_session(peer, profile[2], profile[3], uid)
        first, second = peers
        # A permanece legacy; sólo B pide el catálogo extendido.
        await second.send(b"\xfa\x01\x01\x00\x00\x00\x0f")
        await second.wait(
            lambda frames: any(frame[0] == ServerPacketID.SKILL_CATALOG for frame in frames)
        )
        require(
            not any(frame[0] in {250, 251} for frame in first.frames),
            "legacy sin extensiones espontáneas",
        )
        await first.send(b"\x06")
        await asyncio.sleep(0.05)
        require(
            (await position_of(deps.player_repo, user_ids[0]))["x"] == A_START,
            "WALK incompleto no se ejecuta",
        )
        await first.send(b"\x02")  # Completa un único paso al este.
        await second.send(b"\x06\x01\x77")  # Norte y PING en una sola escritura.
        await second.wait(
            lambda frames: sum(frame[0] == ServerPacketID.PONG for frame in frames) == 1
        )
        require(
            (await position_of(deps.player_repo, user_ids[0]))["x"] == A_START + 1,
            "WALK fragmentado exactamente una vez",
        )
        position = await position_of(deps.player_repo, user_ids[1])
        require((position["x"], position["y"]) == (60, 59), "WALK concatenado exactamente una vez")
        await first.close()
        peers.remove(first)
        async with asyncio.timeout(SMOKE_TIMEOUT_SECONDS):
            await one_left.wait()
        require(
            await client.redis.exists(f"session:{user_ids[1]}:owner") == 1,
            "reserva de B sigue vigente",
        )
        require(
            await client.redis.exists(f"session:{user_ids[0]}:owner") == 0, "reserva de A liberada"
        )
        deps.action_cadence.clock = lambda: 1.0
        await second.send(b"\x06\x03\x77")  # B puede volver al sur después de cerrar A.
        await second.wait(
            lambda frames: sum(frame[0] == ServerPacketID.PONG for frame in frames) == SECOND_PONG
        )
        position = await position_of(deps.player_repo, user_ids[1])
        require((position["x"], position["y"]) == (60, 60), "B conserva su sesión y movimiento")
        return {
            "two_distinct_logins": True,
            "sessions_isolated": True,
            "slot_30_received": True,
            "fragmented_walk_once": True,
            "coalesced_walk_and_ping_once": True,
            "legacy_extended_isolated": True,
            "disconnect_a_preserves_b": True,
            "production_data_used": False,
        }
    finally:
        await asyncio.gather(*(peer.close() for peer in peers), return_exceptions=True)
        if listener is not None:
            listener.close()
            await listener.wait_closed()
        try:
            if handling:
                async with asyncio.timeout(SMOKE_TIMEOUT_SECONDS):
                    await asyncio.gather(*handling)
        finally:
            await close_password_executor()
            await client.disconnect()


def main() -> None:
    """Crea Redis nuevo y ejecuta el smoke acotado, limpiando sólo sus recursos."""
    logging.basicConfig(level=logging.WARNING)
    with RedisSandbox() as sandbox:
        settings = RedisConfig(
            host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file
        )
        result = asyncio.run(asyncio.wait_for(scenario(settings), timeout=45))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
