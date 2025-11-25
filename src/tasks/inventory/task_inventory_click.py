"""Tarea para manejar clicks en el inventario."""

import logging
from typing import TYPE_CHECKING

from src.commands.inventory_click_command import InventoryClickCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.inventory_click_handler import InventoryClickCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskInventoryClick(Task):
    """Maneja el click en un slot del inventario para mostrar información.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int,
        inventory_click_handler: InventoryClickCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de click en inventario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            slot: Slot del inventario (ya validado).
            inventory_click_handler: Handler para el comando de click en inventario.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.slot = slot
        self.inventory_click_handler = inventory_click_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el click en un slot del inventario (solo parsing y delegación).

        El slot ya fue validado por TaskFactory.
        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Verificar que el jugador esté logueado
        if not self.session_data:
            logger.warning("session_data no disponible")
            return

        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de click en inventario sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.inventory_click_handler:
            logger.error("InventoryClickCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = InventoryClickCommand(
            user_id=user_id,
            slot=self.slot,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.inventory_click_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Click en inventario falló: %s", result.error_message or "Error desconocido"
            )
