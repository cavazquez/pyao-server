"""Tarea para meditar y recuperar mana."""

import logging
from typing import TYPE_CHECKING

from src.commands.meditate_command import MeditateCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.meditate_handler import MeditateCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskMeditate(Task):
    """Maneja la meditación para recuperar mana.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        meditate_handler: MeditateCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de meditar.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            meditate_handler: Handler para el comando de meditación.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.meditate_handler = meditate_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el toggle de meditación (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de meditar sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.meditate_handler:
            logger.error("MeditateCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = MeditateCommand(user_id=user_id)

        # Delegar al handler (separación de responsabilidades)
        result = await self.meditate_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Meditación falló: %s", result.error_message or "Error desconocido")
