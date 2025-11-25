"""Handler para comando de creación de clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.create_clan_command import CreateClanCommand

if TYPE_CHECKING:
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class CreateClanCommandHandler(CommandHandler):
    """Handler para comando de creación de clan."""

    def __init__(
        self,
        clan_service: ClanService,
        user_id: int,
        username: str,
    ) -> None:
        """Inicializa el handler.

        Args:
            clan_service: Servicio de clanes.
            user_id: ID del usuario que ejecuta el comando.
            username: Nombre de usuario.
        """
        self.clan_service = clan_service
        self.user_id = user_id
        self.username = username

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de creación de clan.

        Args:
            command: Comando de creación de clan.

        Returns:
            CommandResult con el resultado de la operación.
            Si es exitoso, contiene clan_id y clan_name en data.
            Si falla, contiene error_message.
        """
        if not isinstance(command, CreateClanCommand):
            return CommandResult.error("Comando inválido")

        try:
            clan, message = await self.clan_service.create_clan(
                user_id=self.user_id,
                clan_name=command.clan_name,
                description=command.description,
                username=self.username,
            )

            if clan:
                logger.info("Clan '%s' creado por usuario %s", command.clan_name, self.user_id)
                return CommandResult.ok(data={"clan_id": clan.clan_id, "clan_name": clan.name})
            return CommandResult.error(message)

        except Exception:
            logger.exception("Error al crear clan")
            return CommandResult.error("Error interno al crear clan")
