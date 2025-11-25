"""Task que maneja el paquete COMMERCE_START (84)."""

import logging

from src.tasks.task import Task

logger = logging.getLogger(__name__)


class TaskCommerceStart(Task):
    """Responde a la petición de iniciar comercio desde el cliente.

    El cliente Godot original envía este paquete cuando el jugador usa /COMERCIAR
    (packet 84). Por ahora no hay implementación de comercio directo con NPCs o
    jugadores, así que devolvemos un mensaje claro y evitamos que el paquete caiga
    en TaskNull.
    """

    async def execute(self) -> None:
        """Notifica que la funcionalidad aún no está disponible."""
        logger.info(
            "COMMERCE_START recibido desde %s. Funcionalidad no implementada.",
            self.message_sender.connection.address,
        )
        await self.message_sender.send_console_msg(
            "El comando /COMERCIAR aún no está disponible en esta versión.",
            font_color=7,
        )
