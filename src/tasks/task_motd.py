"""Tarea para mostrar el Mensaje del Día."""

import logging
from typing import TYPE_CHECKING

from src.commands.motd_command import MotdCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.motd_handler import MotdCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskMotd(Task):
    """Tarea que muestra el Mensaje del Día.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        motd_handler: MotdCommandHandler | None = None,
    ) -> None:
        """Inicializa la tarea Motd.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            motd_handler: Handler para el comando de MOTD.
        """
        super().__init__(data, message_sender)
        self.motd_handler = motd_handler

    async def execute(self) -> None:
        """Muestra el Mensaje del Día (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.motd_handler:
            logger.error("MotdCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = MotdCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.motd_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Solicitud de MOTD falló: %s", result.error_message or "Error desconocido")
