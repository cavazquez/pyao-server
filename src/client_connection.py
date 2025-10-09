"""Manejo de conexiones de cliente."""

import asyncio
import logging

from src.msg import build_dice_roll_response

logger = logging.getLogger(__name__)


class ClientConnection:
    """Encapsula la conexión con un cliente y provee métodos para comunicación."""

    def __init__(self, writer: asyncio.StreamWriter) -> None:
        """Inicializa la conexión del cliente.

        Args:
            writer: Stream para enviar datos al cliente.
        """
        self.writer = writer
        self.address = writer.get_extra_info("peername")

    async def send(self, data: bytes) -> None:
        """Envía datos al cliente.

        Args:
            data: Bytes a enviar al cliente.
        """
        self.writer.write(data)
        await self.writer.drain()
        logger.debug("Enviados %d bytes a %s", len(data), self.address)

    async def send_dice_roll(
        self,
        strength: int,
        agility: int,
        intelligence: int,
        charisma: int,
        constitution: int,
    ) -> None:
        """Envía el resultado de una tirada de dados al cliente.

        Args:
            strength: Valor de fuerza (6-18).
            agility: Valor de agilidad (6-18).
            intelligence: Valor de inteligencia (6-18).
            charisma: Valor de carisma (6-18).
            constitution: Valor de constitución (6-18).
        """
        response = build_dice_roll_response(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )
        await self.send(response)

    def close(self) -> None:
        """Cierra la conexión con el cliente."""
        self.writer.close()

    async def wait_closed(self) -> None:
        """Espera a que la conexión se cierre completamente."""
        await self.writer.wait_closed()
