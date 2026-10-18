"""Tarea para mensajes no reconocidos."""

import logging

from src.tasks.task import Task

logger = logging.getLogger(__name__)


class TaskNull(Task):
    """Tarea que se ejecuta cuando no se reconoce el mensaje."""

    async def execute(self) -> None:
        """Loguea información detallada del mensaje no reconocido."""
        logger.warning(
            "Mensaje no reconocido desde %s - Tamaño: %d bytes",
            self.message_sender.address,
            len(self.data),
        )

        # Un fragmento TCP desconocido también puede contener credenciales.
        if self.data:
            logger.warning("Posible PacketID: %d", self.data[0])
