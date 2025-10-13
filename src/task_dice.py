"""Tarea para tirada de dados."""

import logging
import random
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskDice(Task):
    """Tarea que maneja la tirada de dados."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de tirada de dados.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.session_data = session_data

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

        # Guardar atributos en session_data si está disponible
        if self.session_data is not None:
            self.session_data["dice_attributes"] = {
                "strength": strength,
                "agility": agility,
                "intelligence": intelligence,
                "charisma": charisma,
                "constitution": constitution,
            }
            logger.info(
                "Atributos guardados en sesión para %s",
                self.message_sender.connection.address,
            )

        # Enviar resultado usando el enviador de mensajes
        await self.message_sender.send_dice_roll(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )
