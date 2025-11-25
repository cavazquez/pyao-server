"""Handler for PARTY_JOIN packet.

Handles /PARTY command - invites a user to party.
"""

import logging
from typing import TYPE_CHECKING

from src.commands.party_join_command import PartyJoinCommand
from src.network.packet_reader import PacketReader
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.party_join_handler import PartyJoinCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskPartyJoin(Task):
    """Handler for inviting users to party.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        party_join_handler: PartyJoinCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Initialize task with dependencies.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            party_join_handler: Handler para el comando de invitar a party.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.party_join_handler = party_join_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Execute party join (invite) task (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        # Validar que tenemos el handler
        if not self.party_join_handler:
            logger.error("PartyJoinCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        try:
            # Parse packet data
            reader = PacketReader(self.data)

            # Verificar si hay datos suficientes (al menos 4 bytes para int32 de longitud)
            if not reader.validate_remaining_bytes(4):
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTY <nombre>", font_color=7
                )
                return

            # Read target username (cliente Godot usa put_string() que es int32 length + UTF-8)
            target_username = reader.read_godot_put_string(encoding="utf-8")

            if not target_username:
                await self.message_sender.send_console_msg(
                    "Debes especificar un nombre de usuario. Uso: /PARTY <nombre>", font_color=7
                )
                return

            # Crear comando (solo datos)
            command = PartyJoinCommand(user_id=user_id, target_username=target_username)

            # Delegar al handler (separación de responsabilidades)
            result = await self.party_join_handler.handle(command)

            # Manejar resultado si es necesario
            if not result.success:
                logger.debug(
                    "Invitar a party falló: %s", result.error_message or "Error desconocido"
                )

        except Exception:
            logger.exception("Error parsing party invite packet")
            await self.message_sender.send_console_msg(
                "Error al invitar a la party. Intenta nuevamente.", font_color=1
            )
