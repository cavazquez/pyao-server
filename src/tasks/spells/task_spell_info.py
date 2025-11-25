"""Task para manejar el packet SPELL_INFO (35)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.commands.spell_info_command import SpellInfoCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:  # pragma: no cover - hints only
    from src.command_handlers.spell_info_handler import SpellInfoCommandHandler
    from src.messaging.message_sender import MessageSender


logger = logging.getLogger(__name__)

MAX_SPELL_SLOTS = 35


class TaskSpellInfo(Task):
    """Envía información detallada del hechizo solicitado.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        spell_info_handler: SpellInfoCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        *,
        slot: int | None = None,
    ) -> None:
        """Configura la task con dependencias opcionales y datos de sesión."""
        super().__init__(data, message_sender)
        self.spell_info_handler = spell_info_handler
        self.session_data = session_data or {}
        self._validated_slot = slot

    async def execute(self) -> None:
        """Procesa la solicitud y envía la información del hechizo (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("TaskSpellInfo: intento sin sesión activa")
            return

        # Validar que tenemos el handler
        if not self.spell_info_handler:
            logger.error("SpellInfoCommandHandler no disponible")
            return

        slot = self._validated_slot
        if slot is None:
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)

            # Usar nueva API consistente
            slot_result = validator.validate_slot(min_slot=1, max_slot=MAX_SPELL_SLOTS)

            if not slot_result.success:
                await self.message_sender.send_console_msg(
                    slot_result.error_message or "¡Primero selecciona el hechizo!"
                )
                return

            if slot_result.data is None:
                await self.message_sender.send_console_msg("¡Primero selecciona el hechizo!")
                return

            slot = slot_result.data

        # Crear comando (solo datos)
        command = SpellInfoCommand(user_id=user_id, slot=slot)

        # Delegar al handler (separación de responsabilidades)
        result = await self.spell_info_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de información de hechizo falló: %s",
                result.error_message or "Error desconocido",
            )
