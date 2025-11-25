"""Tarea para manejar el movimiento de personajes."""

import logging
from typing import TYPE_CHECKING

from src.commands.walk_command import WalkCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.walk_handler import WalkCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskWalk(Task):
    """Tarea que maneja el movimiento de personajes (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        walk_handler: WalkCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de movimiento.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes al cliente.
            walk_handler: Handler para el comando de movimiento.
            session_data: Datos de sesión compartidos.
        """
        super().__init__(data, message_sender)
        self.walk_handler = walk_handler
        self.session_data = session_data or {}

    def _parse_packet(self) -> int | None:
        """Parsea el paquete de movimiento.

        El formato esperado es:
        - Byte 0: PacketID (WALK = 6)
        - Byte 1: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste)

        Returns:
            Dirección del movimiento o None si hay error.
        """
        try:
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)
            heading = validator.read_heading()

            if validator.has_errors() or heading is None:
                return None
            return heading  # noqa: TRY300
        except ValueError:
            # Packet truncado o inválido
            return None

    async def execute(self) -> None:
        """Procesa el movimiento del personaje (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Parsear y validar packet
        heading = self._parse_packet()
        if heading is None:
            logger.warning(
                "Paquete de movimiento inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        logger.debug(
            "TaskWalk: Recibido WALK con heading=%d desde %s",
            heading,
            self.message_sender.connection.address,
        )

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de movimiento sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.walk_handler:
            logger.error("WalkCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = WalkCommand(
            user_id=user_id,
            heading=heading,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.walk_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Movimiento falló: %s", result.error_message or "Error desconocido")
