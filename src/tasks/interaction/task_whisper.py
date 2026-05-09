"""Task para mensaje susurrado (WHISPER)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.commands.whisper_command import WhisperCommand
from src.constants.gameplay import MAX_CHAT_MESSAGE_LENGTH
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.whisper_handler import WhisperCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)

MAX_WHISPER_RECEIVER_LENGTH = 20


class TaskWhisper(Task):
    """Tarea para procesar mensajes susurrados (WHISPER)."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        whisper_handler: WhisperCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Whisper.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            whisper_handler: Handler para el comando de susurro.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.whisper_handler = whisper_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el susurro (solo parsing y delegación)."""
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning("Intento de susurrar sin usuario logueado")
            return

        receiver, message = self._parse_payload(self.data)
        if receiver is None or message is None:
            logger.warning("Packet WHISPER inválido: falta información")
            return

        if not self.whisper_handler:
            logger.error("WhisperCommandHandler no disponible")
            return

        command = WhisperCommand(user_id=user_id, receiver=receiver, message=message)
        result = await self.whisper_handler.handle(command)

        if not result.success:
            logger.debug("Susurro falló: %s", result.error_message or "Error desconocido")

    @staticmethod
    def _parse_payload(data: bytes) -> tuple[str | None, str | None]:
        """Extrae receiver y message del packet WHISPER.

        Args:
            data: Datos del packet.

        Returns:
            Tupla (receiver, message) o (None, None) si el packet es inválido.
        """
        reader = PacketReader(data)
        validator = PacketValidator(reader)

        receiver_result = validator.validate_string(
            min_length=1, max_length=MAX_WHISPER_RECEIVER_LENGTH, encoding="utf-8"
        )
        if not receiver_result.success:
            return None, None

        message_result = validator.validate_string(
            min_length=1, max_length=MAX_CHAT_MESSAGE_LENGTH, encoding="utf-8"
        )
        if not message_result.success:
            return None, None

        receiver = receiver_result.data if isinstance(receiver_result.data, str) else None
        message = message_result.data if isinstance(message_result.data, str) else None

        return receiver, message
