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

        # Mostrar los primeros bytes en hexadecimal
        hex_preview = " ".join(f"{byte:02X}" for byte in self.data[:32])
        logger.warning("Primeros bytes (hex): %s", hex_preview)

        # Mostrar el primer byte como posible PacketID
        if len(self.data) > 0:
            packet_id = self.data[0]
            logger.warning("Posible PacketID: %d (0x%02X)", packet_id, packet_id)

        # Mostrar representación ASCII (caracteres imprimibles)
        ascii_min = 32
        ascii_max = 127
        ascii_repr = "".join(
            chr(byte) if ascii_min <= byte < ascii_max else "." for byte in self.data[:64]
        )
        logger.warning("Representación ASCII: %s", ascii_repr)
