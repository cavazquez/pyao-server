"""Handler para comando de solicitar detalles del clan."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.request_clan_details_command import RequestClanDetailsCommand
from src.models.clan import MAX_CLAN_MEMBERS, ClanRank

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class RequestClanDetailsCommandHandler(CommandHandler):
    """Handler para comando de solicitar detalles del clan."""

    def __init__(
        self,
        clan_service: ClanService,
        message_sender: MessageSender,
        user_id: int,
    ) -> None:
        """Inicializa el handler.

        Args:
            clan_service: Servicio de clanes.
            message_sender: Enviador de mensajes.
            user_id: ID del usuario que solicita los detalles.
        """
        self.clan_service = clan_service
        self.message_sender = message_sender
        self.user_id = user_id

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de solicitar detalles del clan.

        Args:
            command: Comando de solicitar detalles del clan.

        Returns:
            CommandResult con el resultado de la operación.
        """
        if not isinstance(command, RequestClanDetailsCommand):
            return CommandResult.error("Comando inválido")

        try:
            # Obtener el clan del usuario
            clan = await self.clan_service.clan_repo.get_user_clan(self.user_id)
            if not clan:
                return CommandResult.error("No perteneces a ningún clan")

            # Enviar detalles del clan al cliente
            # TODO: Implementar el envío del paquete CLAN_DETAILS (80)
            # Por ahora, enviar información básica por consola
            member = clan.get_member(self.user_id)
            rank_name = "Líder" if member and member.rank == ClanRank.LEADER else "Miembro"

            await self.message_sender.send_console_msg(
                f"=== Clan: {clan.name} ===",
                font_color=7,  # FONTTYPE_PARTY
            )
            await self.message_sender.send_console_msg(
                f"Líder: {clan.leader_username}",
                font_color=7,
            )
            await self.message_sender.send_console_msg(
                f"Miembros: {clan.member_count}/{MAX_CLAN_MEMBERS}",
                font_color=7,
            )
            await self.message_sender.send_console_msg(
                f"Tu rango: {rank_name}",
                font_color=7,
            )
            if clan.description:
                await self.message_sender.send_console_msg(
                    f"Descripción: {clan.description}",
                    font_color=7,
                )

            # Listar miembros
            if clan.members:
                await self.message_sender.send_console_msg(
                    "Miembros:",
                    font_color=7,
                )
                for member in clan.members.values():
                    rank_str = (
                        "Líder" if member.rank == ClanRank.LEADER else f"Nivel {member.level}"
                    )
                    await self.message_sender.send_console_msg(
                        f"  - {member.username} ({rank_str})",
                        font_color=7,
                    )

            logger.info("Detalles del clan '%s' enviados a user_id %s", clan.name, self.user_id)
            return CommandResult.ok()

        except Exception:
            logger.exception("Error al obtener detalles del clan")
            return CommandResult.error("Error interno al obtener detalles del clan")
