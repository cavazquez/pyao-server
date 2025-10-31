"""Tarea para mostrar la ayuda de comandos disponibles."""

import logging
from typing import TYPE_CHECKING

from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskAyuda(Task):
    """Tarea que muestra la lista de comandos disponibles."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa la tarea Ayuda.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
        """
        super().__init__(data, message_sender)

    async def execute(self) -> None:
        """Muestra la ayuda de comandos disponibles."""
        logger.debug("Solicitud de ayuda desde %s", self.message_sender.connection.address)

        # Mensaje de ayuda con comandos disponibles
        help_message = (
            "--- Comandos Disponibles ---\n"
            "/AYUDA - Muestra esta ayuda\n"
            "/EST - Muestra tus estadisticas\n"
            "/ONLINE - Lista de jugadores conectados\n"
            "/MOTD - Mensaje del dia del servidor\n"
            "/UPTIME - Tiempo de actividad del servidor\n"
            "/INFO - Informacion del servidor\n"
            "/SALIR - Desconectarse del servidor\n"
            "--- Comandos de Party ---\n"
            "/CREARPARTY - Crear una nueva party (nivel 15+)\n"
            "/PARTY <nombre> - Invitar jugador a tu party\n"
            "/ACCEPTPARTY <lider> - Aceptar invitacion de party\n"
            "/SALIRPARTY - Abandonar la party actual\n"
            "/PMSG <mensaje> - Enviar mensaje a tu party\n"
            "/KICK <nombre> - Expulsar miembro (solo lider)\n"
            "/PARTYLIDER <nombre> - Transferir liderazgo (solo lider)\n"
            "--- Informacion ---\n"
            "Usa las teclas de direccion para moverte\n"
            "Escribe en el chat para hablar con otros jugadores"
        )

        # Enviar ayuda línea por línea
        await self.message_sender.send_multiline_console_msg(help_message)
        logger.debug("Ayuda enviada a %s", self.message_sender.connection.address)
