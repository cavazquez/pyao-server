"""Sistema de tareas para procesar mensajes del cliente."""

import logging
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)


class Task(ABC):
    """Clase base para tareas que procesan mensajes del cliente."""

    def __init__(self, data: bytes, message_sender: MessageSender) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
        """
        self.data = data
        self.message_sender = message_sender

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
            self.message_sender.connection.address,
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
            self.message_sender.connection.address,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )

        # Enviar resultado usando el enviador de mensajes
        await self.message_sender.send_dice_roll(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )

        logger.info("Enviado resultado de dados a %s", self.message_sender.connection.address)
