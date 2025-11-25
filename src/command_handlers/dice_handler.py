"""Handler para comando de tirada de dados."""

import logging
import random
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.dice_command import DiceCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class DiceCommandHandler(CommandHandler):
    """Handler para comando de tirada de dados (solo lógica de negocio)."""

    def __init__(
        self,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            message_sender: Enviador de mensajes.
        """
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de tirada de dados (solo lógica de negocio).

        Args:
            command: Comando de tirada de dados.

        Returns:
            Resultado de la ejecución con los atributos generados.
        """
        if not isinstance(command, DiceCommand):
            return CommandResult.error("Comando inválido: se esperaba DiceCommand")

        min_value = command.min_value
        max_value = command.max_value

        logger.info(
            "DiceCommandHandler: tirada de dados con rango %d-%d para %s",
            min_value,
            max_value,
            self.message_sender.connection.address,
        )

        try:
            # Tirar 5 atributos (Fuerza, Agilidad, Inteligencia, Carisma, Constitución)
            strength = random.randint(min_value, max_value)
            agility = random.randint(min_value, max_value)
            intelligence = random.randint(min_value, max_value)
            charisma = random.randint(min_value, max_value)
            constitution = random.randint(min_value, max_value)

            logger.info(
                "DiceCommandHandler: resultado - STR:%d AGI:%d INT:%d CHA:%d CON:%d",
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

            attributes = {
                "strength": strength,
                "agility": agility,
                "intelligence": intelligence,
                "charisma": charisma,
                "constitution": constitution,
            }

            return CommandResult.ok(data={"attributes": attributes})

        except Exception:
            logger.exception("Error al procesar tirada de dados")
            return CommandResult.error("Error interno al procesar tirada de dados")
