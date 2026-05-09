"""Tarea para togglear modo seguro."""

import logging
from typing import TYPE_CHECKING

from src.commands.safe_toggle_command import SafeToggleCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.safe_toggle_handler import SafeToggleCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskSafeToggle(Task):
    """Tarea para togglear el modo seguro del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        safe_toggle_handler: SafeToggleCommandHandler | None = None,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa la tarea SafeToggle.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            safe_toggle_handler: Handler para el comando de modo seguro.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.safe_toggle_handler = safe_toggle_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el toggleo de modo seguro."""
        _ = PacketReader(self.data)

        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "SafeToggle sin sesión activa desde %s",
                self.message_sender.address,
            )
            return

        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        if not self.safe_toggle_handler:
            logger.error("SafeToggleCommandHandler no disponible")
            return

        command = SafeToggleCommand(user_id=user_id_int)
        result = await self.safe_toggle_handler.handle(command)

        if not result.success:
            logger.debug("SafeToggle falló: %s", result.error_message or "Error desconocido")
