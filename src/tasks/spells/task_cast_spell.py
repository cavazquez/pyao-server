"""Tarea para lanzar hechizos."""

import logging
import struct
from typing import TYPE_CHECKING

from src.commands.cast_spell_command import CastSpellCommand
from src.network.capabilities import Capability
from src.network.packet_id import ClientPacketID
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)

# Constantes para el packet CAST_SPELL
MAX_SPELL_SLOTS = 35
MAX_MAP_COORD = 100
CAST_SPELL_MIN_SIZE_OLD = 2  # ID + slot, igual al writer legacy
PACKET_SIZE_WITH_COORDS = 7  # ID distinto + versión + slot + dos i16


class TaskCastSpell(Task):
    """Maneja el lanzamiento de hechizos (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        cast_spell_handler: CastSpellCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de lanzar hechizo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            cast_spell_handler: Handler para el comando de lanzar hechizo.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.cast_spell_handler = cast_spell_handler
        self.session_data = session_data or {}

    def _parse_packet(self) -> tuple[int, int | None, int | None] | None:
        """Parsea el paquete de lanzar hechizo.

        Returns:
            Tupla (slot, target_x, target_y) o None si hay error.
            target_x y target_y pueden ser None si el packet usa formato antiguo.
        """
        if not self.data:
            return None
        if self.data[0] == ClientPacketID.CAST_SPELL:
            if len(self.data) != CAST_SPELL_MIN_SIZE_OLD:
                return None
            slot = self.data[1]
            return (slot, None, None) if 1 <= slot <= MAX_SPELL_SLOTS else None
        if (
            self.data[0] != ClientPacketID.CAST_TARGET
            or len(self.data) != PACKET_SIZE_WITH_COORDS
            or self.data[1] != 1
        ):
            return None
        slot, x, y = struct.unpack_from("<Bhh", self.data, 2)
        if (
            not 1 <= slot <= MAX_SPELL_SLOTS
            or not 1 <= x <= MAX_MAP_COORD
            or not 1 <= y <= MAX_MAP_COORD
        ):
            return None
        connection = self.message_sender.connection
        if (
            connection.is_authenticated is not True
            or not connection.capabilities.enabled & Capability.TARGETED_CAST
        ):
            return None
        return slot, x, y

    async def execute(self) -> None:
        """Procesa el lanzamiento de hechizo (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar longitud mínima del packet
        if len(self.data) < CAST_SPELL_MIN_SIZE_OLD:
            await self.message_sender.send_console_msg(
                f"Packet CAST_SPELL truncado: se esperan al menos {CAST_SPELL_MIN_SIZE_OLD} bytes"
            )
            return

        # Parsear packet
        parsed = self._parse_packet()
        if parsed is None:
            await self.message_sender.send_console_msg("Packet CAST_SPELL inválido")
            return

        slot, target_x, target_y = parsed

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de lanzar hechizo sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.cast_spell_handler:
            logger.error("CastSpellCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = CastSpellCommand(
            user_id=user_id,
            slot=slot,
            target_x=target_x,
            target_y=target_y,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.cast_spell_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Lanzar hechizo falló: %s", result.error_message or "Error desconocido")
