"""Solicitud de extensiones después del login directo de pyao."""

import struct
from typing import TYPE_CHECKING

from src.network.capabilities import CAPABILITIES_VERSION
from src.network.packet_id import ServerPacketID
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.world.world_state import WorldStateService

CAPABILITIES_PACKET_BYTES = 6


class TaskCapabilities(Task):
    """Negocia por conexión sin crear otra cuenta, sesión ni permisos de juego."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        world_state: WorldStateService | None = None,
        session_data: dict[str, int | dict[str, int]] | None = None,
    ) -> None:
        """Mantiene el contrato standalone e inyecta el estado sólo en el servidor."""
        super().__init__(data, message_sender)
        self.world_state = world_state
        self.session_data = session_data or {}

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
        user = SessionManager.get_user_id(self.session_data)
        if self.world_state is not None and user:
            await self.world_state.initial(user, self.message_sender)
