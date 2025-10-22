"""Tarea para mostrar el Mensaje del Día."""

import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class TaskMotd(Task):
    """Tarea que muestra el Mensaje del Día."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        server_repo: ServerRepository | None = None,
    ) -> None:
        """Inicializa la tarea Motd.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            server_repo: Repositorio del servidor para obtener el MOTD.
        """
        super().__init__(data, message_sender)
        self.server_repo = server_repo

    async def execute(self) -> None:
        """Muestra el Mensaje del Día."""
        logger.debug("Solicitud de MOTD desde %s", self.message_sender.connection.address)

        # Obtener MOTD desde el repositorio
        if self.server_repo:
            motd = await self.server_repo.get_motd()
        else:
            # Mensaje por defecto si no hay repositorio
            motd = "» Bienvenido a Argentum Online! «\n• Servidor en desarrollo."

        # Enviar MOTD línea por línea
        await self.message_sender.send_multiline_console_msg(motd)
        logger.info("MOTD enviado a %s", self.message_sender.connection.address)
