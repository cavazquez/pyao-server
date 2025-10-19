"""Componente para enviar mensajes de consola al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg_console import build_console_msg_response, build_error_msg_response

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
        max_log_length = 50
        logger.debug(
            "[%s] Enviando CONSOLE_MSG: %s (color=%d)",
            self.connection.address,
            message[:max_log_length] + "..." if len(message) > max_log_length else message,
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
        """Envía paquete ErrorMsg del protocolo AO estándar.

        Args:
            error_message: Mensaje de error a enviar.
        """
        response = build_error_msg_response(error_message)
        logger.info("[%s] Enviando ERROR_MSG: %s", self.connection.address, error_message)
        await self.connection.send(response)
