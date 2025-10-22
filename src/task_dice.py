"""Tarea para tirada de dados."""

import logging
import random
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class TaskDice(Task):
    """Tarea que maneja la tirada de dados."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]] | None = None,
        server_repo: ServerRepository | None = None,
    ) -> None:
        """Inicializa la tarea de tirada de dados.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            session_data: Datos de sesión compartidos (opcional).
            server_repo: Repositorio del servidor para obtener configuración de dados.
        """
        super().__init__(data, message_sender)
        self.session_data = session_data
        self.server_repo = server_repo

    async def execute(self) -> None:
        """Ejecuta la tirada de dados y envía el resultado al cliente."""
        # Obtener valores mínimo y máximo desde Redis
        if self.server_repo:
            min_value = await self.server_repo.get_dice_min_value()
            max_value = await self.server_repo.get_dice_max_value()
        else:
            # Valores por defecto si no hay repositorio
            min_value = 6
            max_value = 18

        # Tirar 5 atributos (Fuerza, Agilidad, Inteligencia, Carisma, Constitución)
        strength = random.randint(min_value, max_value)  # noqa: S311
        agility = random.randint(min_value, max_value)  # noqa: S311
        intelligence = random.randint(min_value, max_value)  # noqa: S311
        charisma = random.randint(min_value, max_value)  # noqa: S311
        constitution = random.randint(min_value, max_value)  # noqa: S311

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
