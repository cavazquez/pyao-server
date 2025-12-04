"""Tarea para mensajes de chat."""

import logging
from typing import TYPE_CHECKING

from src.commands.talk_command import TalkCommand
from src.constants.gameplay import MAX_CHAT_MESSAGE_LENGTH
from src.network.packet_data import TalkData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.talk_handler import TalkCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)

# Constantes de packet
MIN_TALK_PACKET_SIZE = 3  # PacketID + int16
MAX_MESSAGE_LENGTH = MAX_CHAT_MESSAGE_LENGTH


class TaskTalk(Task):
    """Tarea para procesar mensajes de chat del jugador.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        talk_handler: TalkCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Talk.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            talk_handler: Handler para el comando de mensaje de chat.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.talk_handler = talk_handler
        self.session_data = session_data or {}

    def _parse_packet(self) -> TalkData | None:
        """Parsea el paquete Talk.

        Formato: PacketID (1 byte) + longitud (int16) + mensaje (string UTF-8)

        Returns:
            TalkData con el mensaje validado o None si el paquete es inválido.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        # Usar nueva API consistente
        message_result = validator.validate_string(
            min_length=1, max_length=MAX_MESSAGE_LENGTH, encoding="utf-8"
        )

        if not message_result.success:
            return None

        return TalkData(message=message_result.data or "")

    async def execute(self) -> None:
        """Procesa el mensaje de chat (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        talk_data = self._parse_packet()

        if talk_data is None:
            logger.warning(
                "Paquete Talk inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Mensaje de chat recibido sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        # Convertir user_id a int
        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        # Validar que tenemos el handler
        if not self.talk_handler:
            logger.error("TalkCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = TalkCommand(user_id=user_id_int, message=talk_data.message)

        # Delegar al handler (separación de responsabilidades)
        result = await self.talk_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Mensaje de chat falló: %s", result.error_message or "Error desconocido")
