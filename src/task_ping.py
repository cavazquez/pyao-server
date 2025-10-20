"""Tarea para procesar el ping del cliente."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPing(Task):
    """Tarea que maneja el ping del cliente y responde con pong."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa la tarea Ping.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
        """
        super().__init__(data, message_sender)

    async def execute(self) -> None:
        """Procesa el ping y envía pong."""
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        logger.debug("Ping recibido desde %s", self.message_sender.connection.address)

        # Enviar paquete PONG usando MessageSender
        await self.message_sender.send_pong()
        logger.debug("Pong enviado a %s", self.message_sender.connection.address)
