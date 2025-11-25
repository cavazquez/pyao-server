"""Handler for PARTY_MESSAGE packet.

Handles /PMSG command - sends message to party members.
"""

import logging
from typing import TYPE_CHECKING

from src.commands.party_message_command import PartyMessageCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.party_message_handler import PartyMessageCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPartyMessage(Task):
    """Handler for sending party messages.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_message_handler: PartyMessageCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Initialize task with dependencies.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            party_message_handler: Handler para el comando de enviar mensaje a party.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.party_message_handler = party_message_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Execute party message task (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        # Validar que tenemos el handler
        if not self.party_message_handler:
            logger.error("PartyMessageCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        try:
            # Parse packet data
            reader = PacketReader(self.data)

            # Read message using PacketValidator (UTF-8, same as login)
            validator = PacketValidator(reader)
            message = validator.read_string(min_length=1, max_length=255, encoding="utf-8")

            if validator.has_errors() or message is None:
                await self.message_sender.send_console_msg(
                    "Debes especificar un mensaje. Uso: /PMSG <mensaje>",
                    font_color=7,  # FONTTYPE_PARTY
                )
                return

            # Crear comando (solo datos)
            command = PartyMessageCommand(user_id=user_id, message=message)

            # Delegar al handler (separación de responsabilidades)
            result = await self.party_message_handler.handle(command)

            # Manejar resultado si es necesario
            if not result.success:
                logger.debug(
                    "Enviar mensaje a party falló: %s", result.error_message or "Error desconocido"
                )

        except Exception:
            logger.exception("Error parsing party message packet")
            await self.message_sender.send_console_msg(
                "Error al enviar mensaje a la party. Intenta nuevamente.",
                font_color=1,  # FONTTYPE_FIGHT (red for errors)
            )
