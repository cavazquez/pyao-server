"""Tarea para mostrar el uptime del servidor."""

import logging
import time
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class TaskUptime(Task):
    """Tarea que muestra el tiempo que lleva el servidor corriendo."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        server_repo: ServerRepository | None = None,
    ) -> None:
        """Inicializa la tarea Uptime.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            server_repo: Repositorio del servidor para obtener el timestamp de inicio.
        """
        super().__init__(data, message_sender)
        self.server_repo = server_repo

    async def execute(self) -> None:
        """Muestra el uptime del servidor."""
        logger.debug("Solicitud de uptime desde %s", self.message_sender.connection.address)

        # Obtener timestamp de inicio desde el repositorio
        if self.server_repo:
            start_time = await self.server_repo.get_uptime_start()
            if start_time:
                # Calcular uptime
                current_time = int(time.time())
                uptime_seconds = current_time - start_time

                # Convertir a formato legible
                days = uptime_seconds // 86400
                hours = (uptime_seconds % 86400) // 3600
                minutes = (uptime_seconds % 3600) // 60
                seconds = uptime_seconds % 60

                # Formatear mensaje
                uptime_parts = []
                if days > 0:
                    uptime_parts.append(f"{days} dia{'s' if days != 1 else ''}")
                if hours > 0:
                    uptime_parts.append(f"{hours} hora{'s' if hours != 1 else ''}")
                if minutes > 0:
                    uptime_parts.append(f"{minutes} minuto{'s' if minutes != 1 else ''}")
                if seconds > 0 or not uptime_parts:
                    uptime_parts.append(f"{seconds} segundo{'s' if seconds != 1 else ''}")

                uptime_str = ", ".join(uptime_parts)
                message = f"El servidor lleva activo: {uptime_str}"
            else:
                message = "No se pudo obtener el tiempo de actividad del servidor"
        else:
            message = "Informacion de uptime no disponible"

        # Enviar mensaje
        await self.message_sender.send_console_msg(message)
        logger.debug("Uptime enviado a %s", self.message_sender.connection.address)
