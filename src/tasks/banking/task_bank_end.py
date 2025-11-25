"""Tarea para cerrar la ventana del banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_end_command import BankEndCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.bank_end_handler import BankEndCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskBankEnd(Task):
    """Maneja el cierre de la ventana del banco.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        bank_end_handler: BankEndCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de cerrar banco.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            bank_end_handler: Handler para el comando de cerrar banco.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.bank_end_handler = bank_end_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el cierre del banco (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.bank_end_handler:
            logger.error("BankEndCommandHandler no disponible")
            return

        # Obtener user_id de la sesión (puede ser None si es pre-login)
        user_id = SessionManager.get_user_id(self.session_data)
        user_id_int: int | None = None
        if user_id is not None and not isinstance(user_id, dict):
            user_id_int = int(user_id)

        # Crear comando (solo datos)
        command = BankEndCommand(user_id=user_id_int)

        # Delegar al handler (separación de responsabilidades)
        result = await self.bank_end_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Cierre de banco falló: %s", result.error_message or "Error desconocido")
