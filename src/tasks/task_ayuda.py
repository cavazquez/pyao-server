"""Tarea para mostrar la ayuda de comandos disponibles."""

import logging
from typing import TYPE_CHECKING

from src.commands.ayuda_command import AyudaCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.ayuda_handler import AyudaCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskAyuda(Task):
    """Tarea que muestra la lista de comandos disponibles.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        ayuda_handler: AyudaCommandHandler | None = None,
    ) -> None:
        """Inicializa la tarea Ayuda.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            ayuda_handler: Handler para el comando de ayuda.
        """
        super().__init__(data, message_sender)
        self.ayuda_handler = ayuda_handler

    async def execute(self) -> None:
        """Muestra la ayuda de comandos disponibles (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.ayuda_handler:
            logger.error("AyudaCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = AyudaCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.ayuda_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de ayuda falló: %s", result.error_message or "Error desconocido"
            )
