"""Tarea para mostrar jugadores online."""

import logging
from typing import TYPE_CHECKING

from src.commands.online_command import OnlineCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.online_handler import OnlineCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskOnline(Task):
    """Tarea que maneja la solicitud de jugadores conectados.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        online_handler: OnlineCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Online.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            online_handler: Handler para el comando de lista de jugadores online.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.online_handler = online_handler
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la solicitud de jugadores online (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Solicitud de online recibida sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        # Validar que tenemos el handler
        if not self.online_handler:
            logger.error("OnlineCommandHandler no disponible")
            await self.message_sender.send_console_msg("Error: Servidor no disponible")
            return

        # Crear comando (solo datos)
        command = OnlineCommand(user_id=user_id)

        # Delegar al handler (separación de responsabilidades)
        result = await self.online_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de jugadores online falló: %s",
                result.error_message or "Error desconocido",
            )
