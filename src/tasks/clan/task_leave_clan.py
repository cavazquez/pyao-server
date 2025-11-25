"""Task para salir del clan.

Maneja el paquete CLAN_LEAVE (72) enviado desde la interfaz gráfica del cliente.
"""

import logging
from typing import TYPE_CHECKING

from src.commands.leave_clan_command import LeaveClanCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.leave_clan_handler import LeaveClanCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskLeaveClan(Task):
    """Task para salir del clan.

    Usa Command Pattern: crea el comando y delega al handler.
    El paquete CLAN_LEAVE (72) no tiene datos adicionales, solo el PacketID.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        leave_clan_handler: LeaveClanCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente (solo PacketID).
            message_sender: Enviador de mensajes.
            leave_clan_handler: Handler para el comando de salir del clan.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.leave_clan_handler = leave_clan_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta la tarea de salir del clan."""
        # Obtener user_id de la sesión usando SessionManager (más robusto)
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning(
                "Intento de salir del clan sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_console_msg(
                "Error: Debes estar logueado para salir del clan.",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return

        # Validar que tenemos el handler
        if not self.leave_clan_handler:
            logger.error("LeaveClanCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        # Actualizar user_id en el handler (ya que se crea con user_id=0)
        self.leave_clan_handler.user_id = user_id

        # Crear comando (solo datos)
        command = LeaveClanCommand()

        # Delegar al handler (separación de responsabilidades)
        result = await self.leave_clan_handler.handle(command)

        # Manejar resultado
        if result.success:
            await self.message_sender.send_console_msg(
                result.data.get("message", "Abandonaste el clan")
                if result.data
                else "Abandonaste el clan",
                font_color=7,  # FONTTYPE_PARTY
            )
        else:
            await self.message_sender.send_console_msg(
                result.error_message or "Error al abandonar clan",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
