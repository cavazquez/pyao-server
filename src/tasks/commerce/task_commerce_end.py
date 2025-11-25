"""Tarea para cerrar la ventana de comercio."""

import logging
from typing import TYPE_CHECKING

from src.commands.commerce_end_command import CommerceEndCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.commerce_end_handler import CommerceEndCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskCommerceEnd(Task):
    """Tarea que maneja el cierre de la ventana de comercio.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        commerce_end_handler: CommerceEndCommandHandler | None = None,
    ) -> None:
        """Inicializa la tarea CommerceEnd.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            commerce_end_handler: Handler para el comando de cerrar comercio.
        """
        super().__init__(data, message_sender)
        self.commerce_end_handler = commerce_end_handler

    async def execute(self) -> None:
        """Cierra la ventana de comercio (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.commerce_end_handler:
            logger.error("CommerceEndCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = CommerceEndCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.commerce_end_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Cierre de comercio falló: %s", result.error_message or "Error desconocido"
            )
