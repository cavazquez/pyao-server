"""Tarea para cerrar la ventana de comercio."""

import logging

from src.task import Task

logger = logging.getLogger(__name__)


class TaskCommerceEnd(Task):
    """Tarea que maneja el cierre de la ventana de comercio."""

    async def execute(self) -> None:
        """Cierra la ventana de comercio.

        El cliente envía este paquete cuando el jugador intenta cerrar la ventana de comercio.
        El servidor debe confirmar el cierre enviando el paquete COMMERCE_END.
        """
        logger.debug(
            "Cliente %s solicitó cerrar la ventana de comercio",
            self.message_sender.connection.address,
        )
        # Enviar confirmación para cerrar la ventana
        await self.message_sender.send_commerce_end()
