"""Task para mensaje de grito (YELL)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.commands.yell_command import YellCommand
from src.constants.gameplay import MAX_CHAT_MESSAGE_LENGTH
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.yell_handler import YellCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskYell(Task):
    """Tarea para procesar mensajes de grito (YELL)."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        yell_handler: YellCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Yell.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            yell_handler: Handler para el comando de grito.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.yell_handler = yell_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el grito (solo parsing y delegación)."""
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning("Intento de gritar sin usuario logueado")
            return

        message = self._parse_payload(self.data)
        if message is None:
            logger.warning("Packet YELL inválido: falta información de mensaje")
            return

        if not self.yell_handler:
            logger.error("YellCommandHandler no disponible")
            return

        command = YellCommand(user_id=user_id, message=message)
        result = await self.yell_handler.handle(command)

        if not result.success:
            logger.debug("Grito falló: %s", result.error_message or "Error desconocido")

    @staticmethod
    def _parse_payload(data: bytes) -> str | None:
        """Extrae el mensaje del packet YELL.

        Args:
            data: Datos del packet.

        Returns:
            Mensaje o None si el packet es inválido.
        """
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_string(
            min_length=1, max_length=MAX_CHAT_MESSAGE_LENGTH, encoding="utf-8"
        )

        if not result.success:
            return None

        return result.data if isinstance(result.data, str) else None
