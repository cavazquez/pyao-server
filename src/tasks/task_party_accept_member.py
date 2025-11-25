"""Handler for PARTY_ACCEPT_MEMBER packet.

Handles /ACCEPTPARTY command - accepts a party invitation.
"""

import logging
from typing import TYPE_CHECKING

from src.commands.party_accept_command import PartyAcceptCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.party_accept_handler import PartyAcceptCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPartyAcceptMember(Task):
    """Handler for accepting party invitations.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_accept_handler: PartyAcceptCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Initialize task with dependencies.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            party_accept_handler: Handler para el comando de aceptar invitación.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.party_accept_handler = party_accept_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Execute party acceptance task (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        # Validar que tenemos el handler
        if not self.party_accept_handler:
            logger.error("PartyAcceptCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        try:
            # Parse packet data
            reader = PacketReader(self.data)

            # Read leader username using PacketValidator (UTF-8, same as login)
            validator = PacketValidator(reader)
            leader_username = validator.read_string(min_length=1, max_length=20, encoding="utf-8")

            if validator.has_errors() or leader_username is None:
                await self.message_sender.send_console_msg(
                    "Debes especificar el nombre del líder de la party. Uso: /ACCEPTPARTY <nombre>",
                    font_color=7,
                )
                return

            # Crear comando (solo datos)
            command = PartyAcceptCommand(user_id=user_id, leader_username=leader_username)

            # Delegar al handler (separación de responsabilidades)
            result = await self.party_accept_handler.handle(command)

            # Manejar resultado si es necesario
            if not result.success:
                logger.debug(
                    "Aceptar invitación falló: %s", result.error_message or "Error desconocido"
                )

        except Exception:
            logger.exception("Error parsing party accept packet")
            await self.message_sender.send_console_msg(
                "Error al aceptar la invitación. Intenta nuevamente.", font_color=1
            )
