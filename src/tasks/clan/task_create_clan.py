"""Task para crear un clan.

Maneja el comando /CREARCLAN <nombre> [descripción]
"""

import logging
from typing import TYPE_CHECKING

from src.commands.create_clan_command import CreateClanCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.create_clan_handler import CreateClanCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskCreateClan(Task):
    """Task para crear un clan.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        create_clan_handler: CreateClanCommandHandler | None = None,
        session_data: dict[str, int] | None = None,
    ) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes.
            create_clan_handler: Handler para el comando de crear clan.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.create_clan_handler = create_clan_handler
        self.session_data = session_data or {}

    def _parse_packet(self) -> tuple[str, str] | None:
        """Parsea el paquete de crear clan.

        Formato esperado: PacketID + nombre (string) + descripción opcional (string)

        Returns:
            Tupla (clan_name, description) o None si el paquete es inválido.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        # Leer nombre del clan
        name_result = validator.validate_string(min_length=1, max_length=30, encoding="utf-8")
        if not name_result.success or not name_result.data:
            return None

        clan_name = name_result.data

        # Leer descripción (opcional)
        description = ""
        if validator.reader.has_more_data():
            desc_result = validator.validate_string(min_length=0, max_length=200, encoding="utf-8")
            if desc_result.success and desc_result.data:
                description = desc_result.data

        return (clan_name, description)

    async def execute(self) -> None:
        """Ejecuta la tarea de crear clan."""
        # Obtener user_id de la sesión
        user_id = self.session_data.get("user_id")
        if not user_id:
            await self.message_sender.send_console_msg("Error: No estás autenticado.", font_color=1)
            return

        # Obtener username de la sesión
        username = self.session_data.get("username", f"Player{user_id}")
        if not isinstance(username, str):
            username = f"Player{user_id}"

        # Parsear packet
        parsed = self._parse_packet()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Formato inválido. Uso: /CREARCLAN <nombre> [descripción]",
                font_color=1,
            )
            return

        clan_name, description = parsed

        # Validar que tenemos el handler
        if not self.create_clan_handler:
            logger.error("CreateClanCommandHandler no disponible")
            await self.message_sender.send_console_msg(
                "Error: Servicio no disponible.", font_color=1
            )
            return

        # Crear comando
        command = CreateClanCommand(clan_name=clan_name, description=description)

        # Delegar al handler
        result = await self.create_clan_handler.handle(command)

        # Enviar mensaje de resultado
        if result.success:
            await self.message_sender.send_console_msg(
                result.data.get("message", "Clan creado exitosamente")
                if result.data
                else "Clan creado exitosamente",
                font_color=7,  # FONTTYPE_PARTY (similar color)
            )
        else:
            await self.message_sender.send_console_msg(
                result.error_message or "Error al crear el clan",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
