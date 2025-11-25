"""Tarea para solicitar estadísticas del jugador."""

import logging
from typing import TYPE_CHECKING

from src.commands.request_stats_command import RequestStatsCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.request_stats_handler import RequestStatsCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskRequestStats(Task):
    """Tarea que maneja la solicitud de estadísticas del personaje.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        request_stats_handler: RequestStatsCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea RequestStats.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            request_stats_handler: Handler para el comando de solicitud de estadísticas.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.request_stats_handler = request_stats_handler
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la solicitud de estadísticas del jugador (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Solicitud de estadísticas recibida sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        # Convertir user_id a int
        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        # Validar que tenemos el handler
        if not self.request_stats_handler:
            logger.error("RequestStatsCommandHandler no disponible")
            await self.message_sender.send_console_msg("Error: Repositorio no disponible")
            return

        # Crear comando (solo datos)
        command = RequestStatsCommand(user_id=user_id_int)

        # Delegar al handler (separación de responsabilidades)
        result = await self.request_stats_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de estadísticas falló: %s", result.error_message or "Error desconocido"
            )
