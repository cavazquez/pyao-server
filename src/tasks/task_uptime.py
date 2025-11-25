"""Tarea para mostrar el uptime del servidor."""

import logging
from typing import TYPE_CHECKING

from src.commands.uptime_command import UptimeCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.uptime_handler import UptimeCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskUptime(Task):
    """Tarea que muestra el tiempo que lleva el servidor corriendo.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        uptime_handler: UptimeCommandHandler | None = None,
    ) -> None:
        """Inicializa la tarea Uptime.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            uptime_handler: Handler para el comando de uptime.
        """
        super().__init__(data, message_sender)
        self.uptime_handler = uptime_handler

    async def execute(self) -> None:
        """Muestra el uptime del servidor (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.uptime_handler:
            logger.error("UptimeCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = UptimeCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.uptime_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de uptime falló: %s", result.error_message or "Error desconocido"
            )
