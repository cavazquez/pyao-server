"""Tarea para manejar solicitudes de habilidades del jugador."""

import logging
from typing import TYPE_CHECKING

from src.commands.request_skills_command import RequestSkillsCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.request_skills_handler import RequestSkillsCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskRequestSkills(Task):
    """Maneja la solicitud de habilidades del jugador.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        request_skills_handler: RequestSkillsCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de solicitud de habilidades.

        Args:
            data: Datos del packet (vacío para REQUEST_SKILLS).
            message_sender: Enviador de mensajes.
            request_skills_handler: Handler para el comando de solicitud de habilidades.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.request_skills_handler = request_skills_handler
        self.session_data = session_data

    async def execute(self) -> None:
        """Ejecuta el envío de habilidades del jugador (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning("Intento de solicitar habilidades sin estar logueado")
            return

        # Convertir a int si viene como dict
        if isinstance(user_id, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id_int = int(user_id)

        # Validar que tenemos el handler
        if not self.request_skills_handler:
            logger.error("RequestSkillsCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = RequestSkillsCommand(user_id=user_id_int)

        # Delegar al handler (separación de responsabilidades)
        result = await self.request_skills_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de habilidades falló: %s", result.error_message or "Error desconocido"
            )
