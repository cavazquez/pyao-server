"""Handler for PARTY_CREATE packet.

Handles /CREARPARTY command - creates a new party.
"""

import logging
from typing import TYPE_CHECKING

from src.commands.party_create_command import PartyCreateCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.party_create_handler import PartyCreateCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPartyCreate(Task):
    """Handler for creating a new party.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_create_handler: PartyCreateCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Initialize task with dependencies.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            party_create_handler: Handler para el comando de crear party.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.party_create_handler = party_create_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Execute party creation task (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Get user_id from session
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        # Validar que tenemos el handler
        if not self.party_create_handler:
            logger.error("PartyCreateCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        # Crear comando (solo datos)
        command = PartyCreateCommand(user_id=user_id)

        # Delegar al handler (separación de responsabilidades)
        result = await self.party_create_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Crear party falló: %s", result.error_message or "Error desconocido")
