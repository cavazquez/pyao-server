"""Tarea para retirar oro del banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_extract_gold_command import BankExtractGoldCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskBankExtractGold(Task):
    """Maneja el retiro de oro del banco (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        amount: int,
        bank_extract_gold_handler: BankExtractGoldCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de retiro de oro bancario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            amount: Cantidad de oro a retirar (ya validada).
            bank_extract_gold_handler: Handler para el comando de extraer oro.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.amount = amount
        self.bank_extract_gold_handler = bank_extract_gold_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el retiro de oro del banco (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        El amount ya fue validado por TaskFactory.
        """
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de retiro de oro bancario sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.bank_extract_gold_handler:
            logger.error("BankExtractGoldCommandHandler no disponible")
            await self.message_sender.send_console_msg("Error al retirar oro del banco")
            return

        # Crear comando (solo datos)
        command = BankExtractGoldCommand(user_id=user_id, amount=self.amount)

        # Delegar al handler (separación de responsabilidades)
        result = await self.bank_extract_gold_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Retirar oro falló: %s", result.error_message or "Error desconocido")
