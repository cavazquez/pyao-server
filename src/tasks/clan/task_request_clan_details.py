"""Task para solicitar detalles del clan.

Maneja el paquete CLAN_REQUEST_DETAILS (69) enviado cuando el jugador
hace click en el botón del clan para abrir el menú.
"""

import logging
from typing import TYPE_CHECKING

from src.commands.request_clan_details_command import RequestClanDetailsCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.request_clan_details_handler import RequestClanDetailsCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskRequestClanDetails(Task):
    """Task para solicitar detalles del clan.

    Usa Command Pattern: crea el comando y delega al handler.
    El paquete CLAN_REQUEST_DETAILS (69) no tiene datos adicionales, solo el PacketID.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        request_clan_details_handler: RequestClanDetailsCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente (solo PacketID).
            message_sender: Enviador de mensajes.
            request_clan_details_handler: Handler para el comando de solicitar detalles del clan.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.request_clan_details_handler = request_clan_details_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta la tarea de solicitar detalles del clan."""
        # Obtener user_id de la sesión usando SessionManager (más robusto)
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning(
                "Intento de solicitar detalles del clan sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_console_msg(
                "Error: Debes estar logueado para ver los detalles del clan.",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return

        # Validar que tenemos el handler
        if not self.request_clan_details_handler:
            logger.error("RequestClanDetailsCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        # Actualizar user_id en el handler (ya que se crea con user_id=0)
        self.request_clan_details_handler.user_id = user_id

        # Crear comando (solo datos)
        command = RequestClanDetailsCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.request_clan_details_handler.handle(command)

        # El handler se encarga de enviar los detalles del clan directamente
        # Solo mostramos error si hay alguno
        if not result.success:
            await self.message_sender.send_console_msg(
                result.error_message or "Error al obtener detalles del clan",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
