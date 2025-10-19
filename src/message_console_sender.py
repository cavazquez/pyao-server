"""Componente para enviar mensajes de consola al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import build_console_msg_response

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class ConsoleMessageSender:
    """Maneja el envío de mensajes de consola al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de mensajes de consola.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_console_msg(self, message: str, font_color: int = 7) -> None:
        """Envía un mensaje a la consola del cliente.

        Args:
            message: Mensaje a enviar.
            font_color: Color de la fuente (0-15). Por defecto 7 (gris claro).
        """
        response = build_console_msg_response(message, font_color)
        MAX_LOG_LENGTH = 50
        logger.debug(
            "[%s] Enviando CONSOLE_MSG: %s (color=%d)",
            self.connection.address,
            message[:MAX_LOG_LENGTH] + "..." if len(message) > MAX_LOG_LENGTH else message,
            font_color,
        )
        await self.connection.send(response)

    async def send_multiline_console_msg(self, message: str, font_color: int = 7) -> None:
        """Envía un mensaje multilínea a la consola del cliente.

        Divide el mensaje en líneas y envía cada una por separado.

        Args:
            message: Mensaje multilínea a enviar.
            font_color: Color de la fuente (0-15). Por defecto 7 (gris claro).
        """
        lines = message.split("\n")
        for line in lines:
            if line.strip():  # Solo enviar líneas no vacías
                await self.send_console_msg(line, font_color)

    async def send_error_msg(self, error_message: str) -> None:
        """Envía un mensaje de error a la consola del cliente.

        Args:
            error_message: Mensaje de error a enviar.
        """
        # Color rojo (1) para errores
        await self.send_console_msg(f"Error: {error_message}", font_color=1)
