"""Envío de mensajes relacionados con trabajo/recursos."""

import logging
import struct
from typing import TYPE_CHECKING

from src.packet_id import ServerPacketID

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)

# Índices de mensajes para MULTI_MESSAGE
WORK_REQUEST_TARGET_MSG = 17  # enum Messages.WorkRequestTarget


class WorkMessageSender:
    """Maneja el envío de mensajes relacionados con trabajo."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender.

        Args:
            connection: Conexión del cliente.
        """
        self.connection = connection

    async def send_work_request_target(self, skill_type: int) -> None:
        """Envía mensaje MULTI_MESSAGE con WorkRequestTarget.

        Este mensaje cambia el cursor del cliente al modo de trabajo correspondiente.

        Args:
            skill_type: Tipo de habilidad (9=Talar, 12=Pesca, 13=Minería según enum Skill).
        """
        # MULTI_MESSAGE format:
        # PacketID (1 byte) = 104
        # Message Index (1 byte) = 17 (WorkRequestTarget)
        # arg1 (1 byte) = skill_type
        packet = struct.pack(
            "<BBB",
            ServerPacketID.MULTI_MESSAGE,
            WORK_REQUEST_TARGET_MSG,
            skill_type,
        )
        await self.connection.send(packet)
        logger.debug("MULTI_MESSAGE.WorkRequestTarget enviado (skill_type=%d)", skill_type)
