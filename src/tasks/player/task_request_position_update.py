"""Tarea para procesar la solicitud de actualización de posición del cliente."""

import logging
from typing import TYPE_CHECKING

from src.commands.request_position_update_command import RequestPositionUpdateCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.request_position_update_handler import (
        RequestPositionUpdateCommandHandler,
    )
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskRequestPositionUpdate(Task):
    """Tarea que maneja la solicitud de actualización de posición del cliente.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        request_position_update_handler: RequestPositionUpdateCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea RequestPositionUpdate.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            request_position_update_handler: Handler para el comando de solicitud de posición.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.request_position_update_handler = request_position_update_handler
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la solicitud de actualización de posición (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Solicitud de posición sin estar logueado desde %s",
                self.message_sender.connection.address,
            )
            return

        # Validar que tenemos el handler
        if not self.request_position_update_handler:
            logger.error("RequestPositionUpdateCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = RequestPositionUpdateCommand(user_id=user_id)

        # Delegar al handler (separación de responsabilidades)
        result = await self.request_position_update_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de actualización de posición falló: %s",
                result.error_message or "Error desconocido",
            )
