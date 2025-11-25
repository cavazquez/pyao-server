"""Tarea para mostrar información del servidor."""

import logging
from typing import TYPE_CHECKING

from src.commands.information_command import InformationCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.information_handler import InformationCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskInformation(Task):
    """Tarea que muestra información general del servidor.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        information_handler: InformationCommandHandler | None = None,
    ) -> None:
        """Inicializa la tarea Information.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            information_handler: Handler para el comando de información del servidor.
        """
        super().__init__(data, message_sender)
        self.information_handler = information_handler

    async def execute(self) -> None:
        """Muestra información general del servidor (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.information_handler:
            logger.error("InformationCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = InformationCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.information_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de información falló: %s", result.error_message or "Error desconocido"
            )
