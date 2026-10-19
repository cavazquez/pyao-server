"""RPC real de contraseña y recuperación tras SIGKILL de un Redis AOF propio."""

from __future__ import annotations

import asyncio
import json
import struct
from typing import TYPE_CHECKING

from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_framer import PacketFramer
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.operations.trade_atomic_smoke import settings
from src.operations.two_client_smoke import ProtocolPeer
from src.repositories.account_repository import AccountRepository
from src.security.password_executor import get_password_executor
from src.services.password_change import password_change_status
from src.tasks.task_capabilities import TaskCapabilities
from src.tasks.task_change_password import TaskChangePassword
from src.utils.password_utils import hash_password
from src.utils.redis_client import RedisClient

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig

USERNAME = "PwdSmoke"
OLD_PASSWORD = "Synthetic-Old-P127"  # ruff: ignore[hardcoded-password-string] - sólo cuenta sintética del contenedor propio.
NEW_PASSWORD = "Synthetic-New-P127"  # ruff: ignore[hardcoded-password-string] - sólo cuenta sintética del contenedor propio.
RESULT_ID = 253
CAPABILITIES_ID = 250
CHANGE_ID = 107
EXPECTED_CONFIRMATIONS = 2


def request(identity: str = "", current: str = "", new: str = "") -> bytes:
    """Construye el mismo formato que Godot, sin registrar sus campos.

    Returns:
        Petición 107 versionada.
    """
    return bytes([CHANGE_ID, 1]) + b"".join(
        struct.pack("<H", len(value.encode("latin-1"))) + value.encode("latin-1")
        for value in (identity, current, new)
    )


def replies(frames: list[bytes]) -> list[tuple[str, str, int]]:
    """Lee sólo identificadores y estado de la respuesta, nunca credenciales.

    Returns:
        ID original, próximo ID y estado.
    """
    result = []
    for frame in frames:
        if frame[0] != RESULT_ID:
            continue
        offset, identities = 2, []
        for _ in range(2):
            size = int.from_bytes(frame[offset : offset + 2], "little")
            offset += 2
            identities.append(frame[offset : offset + size].decode("ascii"))
            offset += size
        result.append((identities[0], identities[1], frame[offset]))
    return result


async def verify_credentials(account: AccountRepository, frames: list[bytes]) -> None:
    """Comprueba el mismo verificador usado por login y que las respuestas no contienen claves."""
    require(await account.verify_password(USERNAME, NEW_PASSWORD), "Nueva credencial válida")
    require(
        not await account.verify_password(USERNAME, OLD_PASSWORD),
        "Credencial anterior inválida",
    )
    for frame in frames:
        require(
            OLD_PASSWORD.encode() not in frame and NEW_PASSWORD.encode() not in frame,
            "Ninguna respuesta expone contraseñas",
        )


async def exercise(config: RedisConfig) -> tuple[int, str]:
    """Una fixture autenticada negocia por TCP y recupera un resultado sin reenviar claves.

    Returns:
        Cuenta sintética e ID cuya persistencia se verifica después del reinicio.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    account = AccountRepository(client)
    encoded = await get_password_executor().run(hash_password, OLD_PASSWORD)
    user_id = await account.create_account(USERNAME, encoded, "smoke@example.invalid")
    handlers: set[asyncio.Task[None]] = set()

    async def connected(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task:
            handlers.add(task)
        connection = ClientConnection(reader, writer)
        connection.mark_authenticated()  # Login completo se prueba en two_client_smoke.
        sender = MessageSender(connection)
        framer = PacketFramer()
        try:
            while data := await reader.read(4096):
                framer.feed(data)
                while (frame := framer.next_packet()) is not None:
                    if frame[0] == CAPABILITIES_ID:
                        await TaskCapabilities(frame, sender).execute()
                    else:
                        await TaskChangePassword(
                            frame, sender, account, {"user_id": user_id, "username": USERNAME}
                        ).execute()
        finally:
            connection.close()
            await connection.wait_closed()
            if task:
                handlers.discard(task)

    listener = await asyncio.start_server(connected, "127.0.0.1", 0)
    reader, writer = await asyncio.open_connection(
        "127.0.0.1", listener.sockets[0].getsockname()[1]
    )
    peer = ProtocolPeer(reader, writer)
    try:
        await peer.send(struct.pack("<BBi", CAPABILITIES_ID, 1, 8))
        await peer.wait(lambda frames: any(frame[0] == CAPABILITIES_ID for frame in frames))
        await peer.send(request())
        await peer.wait(lambda frames: bool(replies(frames)))
        identity = replies(peer.frames)[-1][1]
        # Se ignora el primer ack a propósito; la consulta posterior no contiene claves.
        await peer.send(request(identity, OLD_PASSWORD, NEW_PASSWORD) + request(identity))
        await peer.wait(
            lambda frames: (
                sum(item[0] == identity for item in replies(frames)) == EXPECTED_CONFIRMATIONS
            )
        )
        require(
            all(item[2] == 1 for item in replies(peer.frames) if item[0] == identity),
            "Cambio y consulta confirman el mismo resultado",
        )
        await verify_credentials(account, peer.frames)
        return user_id, identity
    finally:
        listener.close()
        await peer.close()
        await asyncio.gather(*handlers)
        await listener.wait_closed()
        await client.disconnect()


async def recover(config: RedisConfig, user_id: int, identity: str) -> None:
    """Comprueba hash y recibo después de recuperar el AOF."""
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        require(
            (await password_change_status(client.redis, USERNAME, user_id, identity))[0] == 1,
            "Recibo durable tras SIGKILL",
        )
        account = AccountRepository(client)
        require(await account.verify_password(USERNAME, NEW_PASSWORD), "Hash nuevo recuperado")
        require(
            not await account.verify_password(USERNAME, OLD_PASSWORD), "Hash viejo no restaurado"
        )
    finally:
        await client.disconnect()


def main() -> None:
    """Sólo mata/reinicia recursos aleatorios creados por este ensayo."""
    with RedisSandbox() as sandbox:
        user_id, identity = asyncio.run(asyncio.wait_for(exercise(settings(sandbox)), timeout=45))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        asyncio.run(asyncio.wait_for(recover(settings(sandbox), user_id, identity), timeout=30))
    print(
        json.dumps(
            {
                "password_cas_atomic": True,
                "lost_ack_query_without_credentials": True,
                "new_credential_valid": True,
                "old_credential_rejected": True,
                "sigkill_recovery": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
