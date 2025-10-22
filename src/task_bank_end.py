"""Tarea para cerrar la ventana del banco."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskBankEnd(Task):
    """Maneja el cierre de la ventana del banco."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de cerrar banco.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el cierre del banco."""
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            # Es normal recibir este paquete antes del login
            logger.debug("BANK_END recibido sin sesión (pre-login)")
            return

        logger.info("user_id %d cerró la ventana del banco", user_id)

        # Enviar confirmación al cliente para cerrar la ventana
        await self.message_sender.send_bank_end()
