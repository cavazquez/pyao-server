"""Task para mover hechizos dentro del libro del jugador."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.commands.move_spell_command import MoveSpellCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

MIN_PACKET_LENGTH = 3

if TYPE_CHECKING:
    from src.command_handlers.move_spell_handler import MoveSpellCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskMoveSpell(Task):
    """Intercambia un hechizo con su slot adyacente.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        move_spell_handler: MoveSpellCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Crea la task con sus dependencias opcionales.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            move_spell_handler: Handler para el comando de mover hechizo.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.move_spell_handler = move_spell_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Intercambia slots si los datos y la sesión son válidos (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning("Intento de mover hechizo sin usuario logueado")
            return

        # Parsear packet
        slot, upwards = self._parse_payload(self.data)

        if slot is None or upwards is None:
            logger.warning("Packet MOVE_SPELL inválido: falta información de movimiento")
            return

        # Validar que tenemos el handler
        if not self.move_spell_handler:
            logger.error("MoveSpellCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = MoveSpellCommand(
            user_id=user_id,
            slot=slot,
            upwards=upwards,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.move_spell_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Mover hechizo falló: %s", result.error_message or "Error desconocido")

    @staticmethod
    def _parse_payload(data: bytes) -> tuple[int | None, bool | None]:
        """Extrae slot y dirección del packet sin prevalidación.

        Args:
            data: Datos del packet.

        Returns:
            Tupla (slot, upwards) o (None, None) si el packet es inválido.
        """
        if len(data) < MIN_PACKET_LENGTH:
            logger.warning("Packet MOVE_SPELL demasiado corto: len=%d", len(data))
            return None, None

        upwards_flag = data[1]
        slot = data[2]

        upwards = upwards_flag != 0
        return slot, upwards
