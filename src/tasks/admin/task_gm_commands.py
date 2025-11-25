"""Tarea para manejar comandos de Game Master (GM)."""

import logging
from typing import TYPE_CHECKING

from src.commands.gm_command import GMCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.gm_command_handler import GMCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskGMCommands(Task):
    """Tarea que maneja comandos de Game Master.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        gm_command_handler: GMCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de comandos GM.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            gm_command_handler: Handler para el comando de Game Master.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.gm_command_handler = gm_command_handler
        self.session_data = session_data

    def _parse_packet(self) -> tuple[int, str, int, int, int] | None:
        """Parsea y valida el paquete de comando GM (teletransporte).

        El formato esperado es:
        - Byte 0: PacketID (GM_COMMANDS = 122)
        - Byte 1: Subcomando GM (ej: WARP_CHAR)
        - String: Username (UTF-16LE con length prefix)
        - Int16: Map ID
        - Byte: X
        - Byte: Y

        Returns:
            Tupla (subcommand, username, map_id, x, y) o None si hay error.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        result = validator.validate_gm_teleport()

        if validator.has_errors():
            logger.warning("Error validando GM_COMMANDS: %s", validator.get_error_message())
            return None

        return result

    async def execute(self) -> None:
        """Ejecuta el comando GM de teletransporte (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Parsear parámetros
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete GM_COMMANDS inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        subcommand, username, map_id, x, y = parsed

        logger.info(
            "Comando GM recibido: subcommand=%d, username=%s, map=%d, pos=(%d,%d)",
            subcommand,
            username,
            map_id,
            x,
            y,
        )

        # Obtener user_id de la sesión
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de comando GM sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Validar que tenemos el handler
        if not self.gm_command_handler:
            logger.error("GMCommandHandler no disponible")
            await self.message_sender.send_console_msg("Error: Servicio no disponible.")
            return

        # Crear comando (solo datos)
        command = GMCommand(
            user_id=user_id,
            subcommand=subcommand,
            username=username,
            map_id=map_id,
            x=x,
            y=y,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.gm_command_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Comando GM falló: %s", result.error_message or "Error desconocido")
