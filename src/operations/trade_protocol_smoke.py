"""Dos sockets reales negocian el intercambio contra Redis AOF descartable."""

import asyncio
import json
import struct
from typing import Any

from redis.exceptions import RedisError

from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_framer import FramingError, PacketFramer
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox
from src.operations.trade_atomic_smoke import settings
from src.operations.two_client_smoke import ProtocolPeer
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.trade_service import TradeService
from src.services.trade_settlement import ParticipantOffer, cancel_settlement, settle_trade
from src.tasks.task_capabilities import TaskCapabilities
from src.tasks.task_trade_action import TaskTradeAction
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient

TRADE_ID = 252
CAPABILITIES_ID = 250
EDITED_REVISION = 2
AFTER_TRADE_FIRST = 80
AFTER_TRADE_SECOND = 120


def latest(frames: list[bytes]) -> dict[str, Any]:
    """Obtiene el último snapshot validado por el framer real.

    Returns:
        Snapshot o diccionario vacío si todavía no llegó.
    """
    states = [json.loads(frame[4:]) for frame in frames if frame[0] == TRADE_ID]
    return states[-1] if states else {}


def action(snapshot: dict[str, Any], intent: int, *, slot: int = 0, amount: int = 0) -> bytes:
    """Construye la misma acción que Godot.

    Returns:
        Paquete de 46 bytes con identidad y revisión.
    """
    return struct.pack(
        "<BBH32siBBi",
        TRADE_ID,
        1,
        32,
        snapshot["id"].encode("ascii"),
        snapshot["revision"],
        intent,
        slot,
        amount,
    )


async def scenario(
    service: TradeService, player: PlayerRepository, peers: list[ProtocolPeer]
) -> None:
    """Recorre el flujo visible y verifica los recursos de ambos participantes."""
    first, second = peers
    require((await service.request_trade(1, "Bob"))[0], "Invitación TCP creada")
    await second.wait(lambda frames: latest(frames).get("state") == "pending")
    await second.send(action(latest(second.frames), 0))
    await first.wait(lambda frames: latest(frames).get("revision") == 1)
    stale = action(latest(first.frames), 3)
    edit = action(latest(first.frames), 2, amount=20)
    await first.send(edit[:7])
    await first.send(edit[7:] + stale)
    await first.wait(
        lambda frames: (
            latest(frames).get("revision") == EDITED_REVISION
            and "cambió" in latest(frames).get("reason", "")
        )
    )
    require(not latest(first.frames)["players"][0][3], "Confirmación obsoleta no aplicada")
    await second.wait(lambda frames: latest(frames).get("revision") == EDITED_REVISION)
    await first.send(action(latest(first.frames), 3))
    await second.send(action(latest(second.frames), 3))
    for peer in peers:
        await peer.wait(lambda frames: latest(frames).get("state") == "completed")
    require(
        await player.get_gold(1) == AFTER_TRADE_FIRST
        and await player.get_gold(2) == AFTER_TRADE_SECOND,
        "Commit TCP mueve oro una vez",
    )
    previous = latest(first.frames)["id"]
    require((await service.request_trade(1, "Bob"))[0], "Nueva sesión después de commit")
    await first.wait(lambda frames: latest(frames).get("id") != previous)
    await second.close()
    await first.wait(lambda frames: latest(frames).get("state") == "cancelled")
    require(
        service.get_session(1) is None and service.get_session(2) is None,
        "Cierre real libera ambos índices",
    )
    # Arbitraje real del journal: sólo un resultado puede ganar.
    frozen = (ParticipantOffer(1, 10, ()), ParticipantOffer(2, 0, ()))
    identity = operation_id()
    committed, cancelled = await asyncio.gather(
        settle_trade(player.redis.redis, identity, frozen, 30, 20),
        cancel_settlement(player.redis.redis, identity, frozen, 30, 20, "Cancelado"),
    )
    require(committed == cancelled, "Cancelación y commit observan el mismo journal")
    require(
        await player.get_gold(1) == (70 if committed["applied"] else 80),
        "Sin compensación duplicada",
    )


async def open_peer(player: PlayerRepository, user: int, port: int) -> ProtocolPeer:
    """Crea una fixture autenticada y negocia por su transporte real.

    Returns:
        Cliente TCP con recepción independiente.
    """
    await player.set_position(user, 49 + user, 50, 1)
    await player.update_gold(user, 100)
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    peer = ProtocolPeer(reader, writer)
    expected = struct.pack("<BBi", 250, 1, 129)
    await peer.send(expected)
    await peer.wait(lambda frames: expected in frames)
    return peer


async def run(sandbox: RedisSandbox) -> None:  # ruff: ignore[too-many-statements] - escenario lineal con limpieza propia.
    """Ensaya revisión obsoleta, commit, cierre de socket y arbitraje en Redis nativo."""
    client = RedisClient()
    await client.connect(settings(sandbox), seed_defaults=False)
    player, inventory, world = PlayerRepository(client), InventoryRepository(client), MapManager()
    service = TradeService(player, inventory, world)
    handlers: set[asyncio.Task[Any]] = set()
    failures: list[Exception] = []
    counter = 0

    async def connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        nonlocal counter
        counter += 1
        user_id = counter
        current = asyncio.current_task()
        if current:
            handlers.add(current)
        connection = ClientConnection(reader, writer)
        connection.mark_authenticated()  # Fixture autenticada; login tiene su propio ensayo TCP.
        sender = MessageSender(connection)
        world.add_player(1, user_id, sender, "Alice" if user_id == 1 else "Bob")
        framer = PacketFramer()
        try:
            while data := await reader.read(4096):
                framer.feed(data)
                while (frame := framer.next_packet()) is not None:
                    if frame[0] == CAPABILITIES_ID:
                        await TaskCapabilities(frame, sender).execute()
                    else:
                        await TaskTradeAction(
                            frame, sender, service, {"user_id": user_id}
                        ).execute()
        except (ConnectionError, RuntimeError, ValueError, FramingError, RedisError) as error:
            failures.append(error)
        finally:
            await service.cancel_trade(user_id, "Un participante se desconectó.")
            world.remove_player(1, user_id)
            connection.close()
            await connection.wait_closed()
            if current:
                handlers.discard(current)

    peers: list[ProtocolPeer] = []
    listener = await asyncio.start_server(connected, "127.0.0.1", 0)
    try:
        peers.extend(
            [await open_peer(player, user, listener.sockets[0].getsockname()[1]) for user in (1, 2)]
        )
        await scenario(service, player, peers)
        require(not failures, "Handlers TCP sin errores")
    finally:
        listener.close()
        for peer in peers:
            if not peer.writer.is_closing():
                await peer.close()
        await asyncio.gather(*handlers)
        await listener.wait_closed()
        await service.close()
        await client.disconnect()


def main() -> None:
    """Opera sólo un contenedor y volumen propios; imprime evidencia sin secretos."""
    with RedisSandbox() as sandbox:
        asyncio.run(asyncio.wait_for(run(sandbox), timeout=50))
    print(
        json.dumps(
            {
                "versioned_tcp_trade": True,
                "stale_confirmation_rejected": True,
                "socket_close_cancels_once": True,
                "native_cancel_commit_arbitration": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
