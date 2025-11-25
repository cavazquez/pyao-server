"""Tarea para vender items a un mercader."""

import logging
from typing import TYPE_CHECKING

from src.commands.commerce_sell_command import CommerceSellCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.commerce_sell_handler import CommerceSellCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskCommerceSell(Task):
    """Tarea que maneja la venta de items a un mercader (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int,
        quantity: int,
        commerce_sell_handler: CommerceSellCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de venta.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            slot: Slot del inventario a vender (ya validado).
            quantity: Cantidad a vender (ya validada).
            commerce_sell_handler: Handler para el comando de vender item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.slot = slot
        self.quantity = quantity
        self.commerce_sell_handler = commerce_sell_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa la venta de un item al mercader (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        Los datos (slot, quantity) ya fueron validados por TaskFactory.
        """
        logger.debug(
            "Cliente %s intenta vender: slot=%d, quantity=%d",
            self.message_sender.connection.address,
            self.slot,
            self.quantity,
        )

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if not user_id:
            await self.message_sender.send_console_msg("Error: Sesión no válida")
            return

        # Validar que tenemos el handler
        if not self.commerce_sell_handler:
            logger.error("CommerceSellCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = CommerceSellCommand(user_id=user_id, slot=self.slot, quantity=self.quantity)

        # Delegar al handler (separación de responsabilidades)
        result = await self.commerce_sell_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Vender item falló: %s", result.error_message or "Error desconocido")
