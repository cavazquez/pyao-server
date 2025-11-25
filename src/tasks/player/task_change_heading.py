"""Tarea para manejar el cambio de dirección del personaje."""

import logging
from typing import TYPE_CHECKING

from src.commands.change_heading_command import ChangeHeadingCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.change_heading_handler import ChangeHeadingCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)

# Constantes para validación de paquetes
MIN_CHANGE_HEADING_PACKET_SIZE = 2


class TaskChangeHeading(Task):
    """Tarea que maneja el cambio de dirección del personaje sin moverse.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        change_heading_handler: ChangeHeadingCommandHandler | None = None,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa la tarea de cambio de dirección.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            change_heading_handler: Handler para el comando de cambio de dirección.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.change_heading_handler = change_heading_handler
        self.session_data = session_data or {}

    def _parse_packet(self) -> int | None:
        """Parsea el paquete de cambio de dirección.

        El formato esperado es:
        - Byte 0: PacketID (CHANGE_HEADING = 37)
        - Byte 1: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste)

        Returns:
            Dirección o None si hay error.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        heading = validator.read_heading()

        if validator.has_errors() or heading is None:
            return None

        return heading

    async def execute(self) -> None:
        """Ejecuta el cambio de dirección del personaje (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Parsear dirección
        heading = self._parse_packet()
        if heading is None:
            logger.warning(
                "Paquete de cambio de dirección inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Obtener user_id de la sesión
        if "user_id" not in self.session_data:
            logger.warning(
                "Intento de cambio de dirección sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Validar que tenemos el handler
        if not self.change_heading_handler:
            logger.error("ChangeHeadingCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = ChangeHeadingCommand(user_id=user_id, heading=heading)

        # Delegar al handler (separación de responsabilidades)
        result = await self.change_heading_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Cambio de dirección falló: %s", result.error_message or "Error desconocido"
            )
