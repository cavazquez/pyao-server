"""Handler for PARTY_KICK packet.

Handles party member kick (leader only).
"""

import logging
from typing import TYPE_CHECKING

from src.commands.party_kick_command import PartyKickCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.party_kick_handler import PartyKickCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPartyKick(Task):
    """Handler for kicking party members.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_kick_handler: PartyKickCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Initialize task with dependencies.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            party_kick_handler: Handler para el comando de expulsar miembro.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.party_kick_handler = party_kick_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Execute party kick task (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        # Validar que tenemos el handler
        if not self.party_kick_handler:
            logger.error("PartyKickCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        try:
            # Parse packet data
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)

            # Read target username using PacketValidator (UTF-8, same as login)
            target_username = validator.read_string(min_length=1, max_length=20, encoding="utf-8")

            if validator.has_errors() or target_username is None:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /KICK <nombre>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return

            # Crear comando (solo datos)
            command = PartyKickCommand(user_id=user_id, target_username=target_username)

            # Delegar al handler (separación de responsabilidades)
            result = await self.party_kick_handler.handle(command)

            # Manejar resultado si es necesario
            if not result.success:
                logger.debug(
                    "Expulsar miembro falló: %s", result.error_message or "Error desconocido"
                )

        except Exception:
            logger.exception("Error parsing party kick packet")
            await self.message_sender.send_console_msg(
                "Error al expulsar miembro. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
