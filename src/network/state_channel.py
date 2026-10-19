"""Frames JSON ASCII acotados, exclusivos de conexiones con capacidad negociada."""

import json
import struct
from typing import TYPE_CHECKING, Any, Protocol

from src.network.capabilities import Capability

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection

STATE_PACKET_ID = 248
MAX_STATE_BYTES = 3800


class StateSender(Protocol):
    """Emisores que pertenecen a una conexión concreta del servidor."""

    connection: ClientConnection


async def send_state(
    sender: StateSender,
    kind: str,
    data: dict[str, Any],
    *,
    identity: str = "",
    revision: str = "",
) -> None:
    """Congela identidad de conexión, secuencia y contenido antes del primer await.

    Raises:
        ValueError: Si una página excede el contrato de 4096 bytes del stream.
    """
    connection = sender.connection
    if (
        not connection.is_authenticated
        or not connection.capabilities.enabled & Capability.WORLD_STATE
    ):
        return
    sequence = connection.state_sequence + 1
    text = json.dumps(
        {
            "epoch": connection.state_epoch,
            "sequence": sequence,
            "kind": kind,
            "id": identity,
            "revision": revision,
            "data": data,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    if len(text) > MAX_STATE_BYTES:
        message = "La página de estado excede el límite del protocolo"
        raise ValueError(message)
    connection.state_sequence = sequence
    await connection.send(struct.pack("<BBH", STATE_PACKET_ID, 1, len(text)) + text)
