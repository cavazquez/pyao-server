"""Tarea para procesar el ping del cliente."""

import logging
from typing import TYPE_CHECKING

from src.commands.ping_command import PingCommand
from src.network.packet_reader import PacketReader
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.ping_handler import PingCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPing(Task):
    """Tarea que maneja el ping del cliente y responde con pong.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        ping_handler: PingCommandHandler | None = None,
    ) -> None:
        """Inicializa la tarea Ping.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            ping_handler: Handler para el comando de ping.
        """
        super().__init__(data, message_sender)
        self.ping_handler = ping_handler

    async def execute(self) -> None:
        """Procesa el ping y envía pong (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Validar que tenemos el handler
        if not self.ping_handler:
            logger.error("PingCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = PingCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.ping_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Ping falló: %s", result.error_message or "Error desconocido")
