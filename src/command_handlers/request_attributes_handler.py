"""Handler para comando de solicitud de atributos."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.request_attributes_command import RequestAttributesCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class RequestAttributesCommandHandler(CommandHandler):
    """Handler para comando de solicitud de atributos (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores (puede ser None si se usan atributos de sesión).
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de solicitud de atributos (solo lógica de negocio).

        Args:
            command: Comando de solicitud de atributos.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, RequestAttributesCommand):
            return CommandResult.error("Comando inválido: se esperaba RequestAttributesCommand")

        user_id = command.user_id

        logger.info(
            "RequestAttributesCommandHandler: solicitud de atributos para user_id %s",
            user_id if user_id is not None else "sesión",
        )

        try:
            # Si hay atributos desde sesión (creación de personaje), usarlos
            if command.dice_attributes is not None:
                dice_attrs: dict[str, int] = command.dice_attributes
                logger.info(
                    "Enviando atributos desde sesión: STR=%d AGI=%d INT=%d CHA=%d CON=%d",
                    dice_attrs["strength"],
                    dice_attrs["agility"],
                    dice_attrs["intelligence"],
                    dice_attrs["charisma"],
                    dice_attrs["constitution"],
                )

                await self.message_sender.send_attributes(
                    strength=dice_attrs["strength"],
                    agility=dice_attrs["agility"],
                    intelligence=dice_attrs["intelligence"],
                    charisma=dice_attrs["charisma"],
                    constitution=dice_attrs["constitution"],
                )

                return CommandResult.ok(data={"attributes": dice_attrs, "from_session": True})

            # Si no hay user_id, retornar error
            if user_id is None:
                await self.message_sender.send_attributes(0, 0, 0, 0, 0)
                return CommandResult.error("user_id es None")

            # Obtener atributos desde el repositorio
            if not self.player_repo:
                logger.error("PlayerRepository no disponible para obtener atributos")
                await self.message_sender.send_attributes(0, 0, 0, 0, 0)
                return CommandResult.error("PlayerRepository no disponible")

            attributes: dict[str, int] | None = await self.player_repo.get_attributes(user_id)

            if attributes is not None:
                logger.info(
                    "Enviando atributos desde repositorio para user_id %d: "
                    "STR=%d AGI=%d INT=%d CHA=%d CON=%d",
                    user_id,
                    attributes["strength"],
                    attributes["agility"],
                    attributes["intelligence"],
                    attributes["charisma"],
                    attributes["constitution"],
                )

                await self.message_sender.send_attributes(
                    strength=attributes["strength"],
                    agility=attributes["agility"],
                    intelligence=attributes["intelligence"],
                    charisma=attributes["charisma"],
                    constitution=attributes["constitution"],
                )

                return CommandResult.ok(data={"user_id": user_id, "attributes": attributes})
            logger.warning(
                "No se encontraron atributos en repositorio para user_id %d",
                user_id,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return CommandResult.error("No se encontraron atributos")

        except Exception:
            logger.exception("Error al procesar solicitud de atributos")
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return CommandResult.error("Error interno al procesar atributos")
