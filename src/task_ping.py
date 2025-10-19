"""Tarea para procesar el ping del cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import build_pong_response
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
        logger.debug("Ping recibido desde %s", self.message_sender.connection.address)

        # Construir y enviar paquete PONG
        pong_packet = build_pong_response()
        await self.message_sender.connection.send(pong_packet)
        logger.debug("Pong enviado a %s", self.message_sender.connection.address)
