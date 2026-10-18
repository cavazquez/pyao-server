"""Solicitud de extensiones después del login directo de pyao."""

import struct

from src.network.capabilities import CAPABILITIES_VERSION
from src.network.packet_id import ServerPacketID
from src.tasks.task import Task

CAPABILITIES_PACKET_BYTES = 6


class TaskCapabilities(Task):
    """Negocia por conexión sin crear otra cuenta, sesión ni permisos de juego."""

    async def execute(self) -> None:
        """Ignora pedidos no autenticados, mal formados o fuera de la ventana."""
        connection = self.message_sender.connection
        if not connection.is_authenticated or len(self.data) != CAPABILITIES_PACKET_BYTES:
            return
        version, requested = struct.unpack("<Bi", self.data[1:])
        enabled = connection.capabilities.negotiate(version, requested)
        if enabled is None:
            return
        await connection.send(
            struct.pack("<BBi", ServerPacketID.CAPABILITIES, CAPABILITIES_VERSION, enabled)
        )
