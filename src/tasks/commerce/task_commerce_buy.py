"""Tarea para comprar items de un mercader."""

import logging
from typing import TYPE_CHECKING

from src.commands.commerce_buy_command import CommerceBuyCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.commerce_buy_handler import CommerceBuyCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskCommerceBuy(Task):
    """Tarea que maneja la compra de items de un mercader (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int,
        quantity: int,
        commerce_buy_handler: CommerceBuyCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de compra.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            slot: Slot del mercader a comprar (ya validado).
            quantity: Cantidad a comprar (ya validada).
            commerce_buy_handler: Handler para el comando de comprar item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.slot = slot
        self.quantity = quantity
        self.commerce_buy_handler = commerce_buy_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa la compra de un item del mercader (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        Los datos (slot, quantity) ya fueron validados por TaskFactory.
        """
        logger.debug(
            "Cliente %s intenta comprar: slot=%d, quantity=%d",
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
        if not self.commerce_buy_handler:
            logger.error("CommerceBuyCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = CommerceBuyCommand(user_id=user_id, slot=self.slot, quantity=self.quantity)

        # Delegar al handler (separación de responsabilidades)
        result = await self.commerce_buy_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Comprar item falló: %s", result.error_message or "Error desconocido")
