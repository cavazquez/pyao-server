"""Task para manejar recogida de items del suelo."""

import logging
from typing import TYPE_CHECKING

from src.commands.pickup_command import PickupCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.pickup_handler import PickupCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPickup(Task):
    """Maneja el packet PICKUP del cliente (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        pickup_handler: PickupCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el task.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            pickup_handler: Handler para el comando de recoger item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.pickup_handler = pickup_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa la recogida de un item del suelo (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de recoger item sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.pickup_handler:
            logger.error("PickupCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = PickupCommand(user_id=user_id)

        # Delegar al handler (separación de responsabilidades)
        result = await self.pickup_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Recoger item falló: %s", result.error_message or "Error desconocido")
