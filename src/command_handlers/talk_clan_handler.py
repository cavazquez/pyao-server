"""Handler especializado para comandos de clan desde el chat."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.accept_clan_handler import AcceptClanCommandHandler
from src.command_handlers.create_clan_handler import CreateClanCommandHandler
from src.command_handlers.demote_clan_member_handler import DemoteClanMemberCommandHandler
from src.command_handlers.invite_clan_handler import InviteClanCommandHandler
from src.command_handlers.kick_clan_member_handler import KickClanMemberCommandHandler
from src.command_handlers.leave_clan_handler import LeaveClanCommandHandler
from src.command_handlers.promote_clan_member_handler import PromoteClanMemberCommandHandler
from src.command_handlers.reject_clan_handler import RejectClanCommandHandler
from src.command_handlers.transfer_clan_leadership_handler import (
    TransferClanLeadershipCommandHandler,
)
from src.commands.accept_clan_command import AcceptClanCommand
from src.commands.create_clan_command import CreateClanCommand
from src.commands.demote_clan_member_command import DemoteClanMemberCommand
from src.commands.invite_clan_command import InviteClanCommand
from src.commands.kick_clan_member_command import KickClanMemberCommand
from src.commands.leave_clan_command import LeaveClanCommand
from src.commands.promote_clan_member_command import PromoteClanMemberCommand
from src.commands.reject_clan_command import RejectClanCommand
from src.commands.transfer_clan_leadership_command import TransferClanLeadershipCommand

if TYPE_CHECKING:
    from src.commands.talk_command import TalkCommand
    from src.messaging.message_sender import MessageSender
    from src.services.clan_service import ClanService

logger = logging.getLogger(__name__)


class TalkClanHandler:
    """Handler especializado para comandos de clan desde el chat."""

    def __init__(
        self,
        clan_service: ClanService | None,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None,
    ) -> None:
        """Inicializa el handler de comandos de clan.

        Args:
            clan_service: Servicio de clanes.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.
        """
        self.clan_service = clan_service
        self.message_sender = message_sender
        self.session_data = session_data if session_data is not None else {}

    async def handle_clan_command(self, user_id: int, command: TalkCommand) -> None:  # noqa: PLR0915, PLR0914
        """Maneja comandos de clan desde el chat.

        Args:
            user_id: ID del usuario que ejecuta el comando.
            command: Comando de chat que contiene el comando de clan.
        """
        if not self.clan_service:
            await self.message_sender.send_console_msg(
                "Sistema de clanes no disponible",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return

        parsed = command.parse_clan_command()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Comando de clan inválido. Usa /AYUDA para ver comandos disponibles.",
                font_color=1,
            )
            return

        cmd_name, args = parsed

        # Obtener username de la sesión
        username = "Desconocido"
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        try:
            if cmd_name == "CREARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /CREARCLAN <nombre> [descripción]",
                        font_color=1,
                    )
                    return

                clan_name = args[0]
                description = " ".join(args[1:]) if len(args) > 1 else ""

                create_handler = CreateClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                    username=username,
                )
                clan_command = CreateClanCommand(clan_name=clan_name, description=description)
                result = await create_handler.handle(clan_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        f"Clan '{clan_name}' creado exitosamente",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al crear el clan",
                        font_color=1,
                    )

            elif cmd_name == "INVITARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /INVITARCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                invite_handler = InviteClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                invite_command = InviteClanCommand(target_username=target_username)
                result = await invite_handler.handle(invite_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Invitación enviada")
                        if result.data
                        else "Invitación enviada",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al invitar",
                        font_color=1,
                    )

            elif cmd_name == "ACEPTARCLAN":
                accept_handler = AcceptClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                accept_command = AcceptClanCommand()
                result = await accept_handler.handle(accept_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        f"Te uniste al clan '{result.data.get('clan_name', '')}'"
                        if result.data
                        else "Te uniste al clan",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al aceptar invitación",
                        font_color=1,
                    )

            elif cmd_name == "RECHAZARCLAN":
                reject_handler = RejectClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                reject_command = RejectClanCommand()
                result = await reject_handler.handle(reject_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Invitación rechazada")
                        if result.data
                        else "Invitación rechazada",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al rechazar invitación",
                        font_color=1,
                    )

            elif cmd_name == "SALIRCLAN":
                leave_handler = LeaveClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                leave_command = LeaveClanCommand()
                result = await leave_handler.handle(leave_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Abandonaste el clan")
                        if result.data
                        else "Abandonaste el clan",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al abandonar clan",
                        font_color=1,
                    )

            elif cmd_name == "EXPULSARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /EXPULSARCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                kick_handler = KickClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                kick_command = KickClanMemberCommand(target_username=target_username)
                result = await kick_handler.handle(kick_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Miembro expulsado")
                        if result.data
                        else "Miembro expulsado",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al expulsar miembro",
                        font_color=1,
                    )

            elif cmd_name == "PROMOVERCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /PROMOVERCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                promote_handler = PromoteClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                promote_command = PromoteClanMemberCommand(target_username=target_username)
                result = await promote_handler.handle(promote_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Miembro promovido")
                        if result.data
                        else "Miembro promovido",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al promover miembro",
                        font_color=1,
                    )

            elif cmd_name == "DEGRADARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /DEGRADARCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                demote_handler = DemoteClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                demote_command = DemoteClanMemberCommand(target_username=target_username)
                result = await demote_handler.handle(demote_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Miembro degradado")
                        if result.data
                        else "Miembro degradado",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al degradar miembro",
                        font_color=1,
                    )

            elif cmd_name == "TRANSFERIRLIDERAZGO":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /TRANSFERIRLIDERAZGO <usuario>",
                        font_color=1,
                    )
                    return

                new_leader_username = args[0]

                transfer_handler = TransferClanLeadershipCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                transfer_command = TransferClanLeadershipCommand(
                    new_leader_username=new_leader_username
                )
                result = await transfer_handler.handle(transfer_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Liderazgo transferido")
                        if result.data
                        else "Liderazgo transferido",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al transferir liderazgo",
                        font_color=1,
                    )

            elif cmd_name == "CLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /CLAN <mensaje>",
                        font_color=1,
                    )
                    return

                clan_message = " ".join(args)
                error_msg = await self.clan_service.send_clan_message(user_id, clan_message)

                if error_msg:
                    await self.message_sender.send_console_msg(error_msg, font_color=1)
                # Si no hay error, el mensaje ya se envió a todos los miembros

            else:
                await self.message_sender.send_console_msg(
                    f"Comando '{cmd_name}' no reconocido. Usa /AYUDA para ver comandos.",
                    font_color=1,
                )

        except Exception:
            logger.exception("Error al procesar comando de clan")
            await self.message_sender.send_console_msg(
                "Error interno al procesar comando de clan",
                font_color=1,
            )
