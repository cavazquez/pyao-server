"""Tarea para procesar mensajes de chat."""

import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)

# Constantes
MIN_TALK_PACKET_SIZE = 3  # PacketID + int16


class TaskTalk(Task):
    """Tarea para procesar mensajes de chat del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Talk.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.session_data = session_data

    def _parse_packet(self) -> str | None:
        """Parsea el paquete Talk.

        Formato: PacketID (1 byte) + longitud (int16) + mensaje (string UTF-8)

        Returns:
            Mensaje de chat o None si el paquete es inválido.
        """
        try:
            if len(self.data) < MIN_TALK_PACKET_SIZE:
                return None

            # Leer longitud del mensaje (int16, little-endian)
            msg_length = int.from_bytes(self.data[1:3], byteorder="little", signed=False)

            # Verificar que hay suficientes bytes
            if len(self.data) < 3 + msg_length:
                return None

            # Leer y retornar mensaje
            return self.data[3 : 3 + msg_length].decode("utf-8")

        except (ValueError, UnicodeDecodeError):
            return None

    async def execute(self) -> None:
        """Procesa el mensaje de chat."""
        message = self._parse_packet()

        if message is None:
            logger.warning(
                "Paquete Talk inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Obtener user_id de la sesión
        user_id = None
        if self.session_data:
            user_id = self.session_data.get("user_id")

        if user_id is None:
            logger.warning(
                "Mensaje de chat recibido sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        logger.info(
            "Mensaje de chat de user_id %d: %s",
            user_id,
            message,
        )

        # Por ahora solo logueamos el mensaje
        # En el futuro se implementará broadcast a jugadores cercanos
