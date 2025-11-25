"""Tarea para depositar oro en el banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_deposit_gold_command import BankDepositGoldCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskBankDepositGold(Task):
    """Maneja el depósito de oro en el banco (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        amount: int,
        bank_deposit_gold_handler: BankDepositGoldCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de depósito de oro bancario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            amount: Cantidad de oro a depositar (ya validada).
            bank_deposit_gold_handler: Handler para el comando de depositar oro.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.amount = amount
        self.bank_deposit_gold_handler = bank_deposit_gold_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el depósito de oro en el banco (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        El amount ya fue validado por TaskFactory.
        """
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de depósito de oro bancario sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.bank_deposit_gold_handler:
            logger.error("BankDepositGoldCommandHandler no disponible")
            await self.message_sender.send_console_msg("Error al depositar oro en el banco")
            return

        # Crear comando (solo datos)
        command = BankDepositGoldCommand(user_id=user_id, amount=self.amount)

        # Delegar al handler (separación de responsabilidades)
        result = await self.bank_deposit_gold_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Depositar oro falló: %s", result.error_message or "Error desconocido")
