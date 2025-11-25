"""Tarea para manejar el uso de ítems del inventario."""

import logging
from typing import TYPE_CHECKING

from src.commands.use_item_command import UseItemCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.use_item_handler import UseItemCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskUseItem(Task):
    """Maneja el uso de un ítem del inventario (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int,
        use_item_handler: UseItemCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Initialize a TaskUseItem instance with dependencies and context.

        Args:
            data: Packet payload associated with the USE_ITEM request.
            message_sender: Facade used to communicate responses to the client.
            slot: Inventory slot requested by the client (ya validado).
            use_item_handler: Handler para el comando de usar item.
            session_data: Session context dictionary keyed by user-related data. Optional.
        """
        super().__init__(data, message_sender)
        self.slot = slot
        self.use_item_handler = use_item_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el uso de un ítem del inventario (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de usar ítem sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.use_item_handler:
            logger.error("UseItemCommandHandler no disponible")
            return

        # Obtener username si está disponible (para actualización visual)
        username = None
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        # Crear comando (solo datos)
        command = UseItemCommand(
            user_id=user_id,
            slot=self.slot,
            username=username,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.use_item_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Usar item falló: %s", result.error_message or "Error desconocido")
