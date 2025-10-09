"""Sistema de tareas para procesar mensajes del cliente."""

import asyncio
import logging
import random
from abc import ABC, abstractmethod

from src.msg import build_dice_roll_response

logger = logging.getLogger(__name__)


class Task(ABC):
    """Clase base para tareas que procesan mensajes del cliente."""

    def __init__(self, data: bytes, writer: asyncio.StreamWriter) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente.
            writer: Stream para enviar respuestas al cliente.
        """
        self.data = data
        self.writer = writer
        self.client_addr = writer.get_extra_info("peername")

    @abstractmethod
    async def execute(self) -> None:
        """Ejecuta la tarea. Debe ser implementado por las subclases."""
        ...


class TaskNull(Task):
    """Tarea que se ejecuta cuando no se reconoce el mensaje."""

    async def execute(self) -> None:
        """Loguea información detallada del mensaje no reconocido."""
        logger.warning(
            "Mensaje no reconocido desde %s - Tamaño: %d bytes",
            self.client_addr,
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


class TaskDice(Task):
    """Tarea que maneja la tirada de dados."""

    async def execute(self) -> None:
        """Ejecuta la tirada de dados y envía el resultado al cliente."""
        # Tirar 5 atributos (Fuerza, Agilidad, Inteligencia, Carisma, Constitución)
        strength = random.randint(6, 18)  # noqa: S311
        agility = random.randint(6, 18)  # noqa: S311
        intelligence = random.randint(6, 18)  # noqa: S311
        charisma = random.randint(6, 18)  # noqa: S311
        constitution = random.randint(6, 18)  # noqa: S311

        logger.info(
            "Cliente %s tiró dados - STR:%d AGI:%d INT:%d CHA:%d CON:%d",
            self.client_addr,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )

        # Construir paquete de respuesta
        response = build_dice_roll_response(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )

        # Enviar respuesta al cliente
        self.writer.write(response)
        await self.writer.drain()

        logger.info("Enviado resultado de dados a %s", self.client_addr)
