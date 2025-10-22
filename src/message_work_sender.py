"""Envío de mensajes relacionados con trabajo/recursos."""

import logging
import struct
from typing import TYPE_CHECKING

from src.packet_id import ServerPacketID

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class WorkMessageSender:
    """Maneja el envío de mensajes relacionados con trabajo."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender.

        Args:
            connection: Conexión del cliente.
        """
        self.connection = connection

    async def send_work_request_target(self, skill_type: int) -> None:
        """Envía paquete WORK_REQUEST_TARGET para solicitar objetivo de trabajo.

        Este packet cambia el cursor del cliente al modo de trabajo correspondiente.

        Args:
            skill_type: Tipo de habilidad (1=Talar, 2=Minería, 3=Pesca).
        """
        packet = struct.pack(
            "<BB",
            ServerPacketID.WORK_REQUEST_TARGET,
            skill_type,
        )
        await self.connection.send(packet)
        logger.debug("WORK_REQUEST_TARGET enviado (skill_type=%d)", skill_type)
