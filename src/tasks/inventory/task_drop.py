"""Task para manejar el drop de items del inventario al suelo."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.commands.drop_command import DropCommand
from src.config import config
from src.config.config_manager import ConfigManager
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.drop_handler import DropCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskDrop(Task):
    """Maneja el packet DROP del cliente (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        drop_handler: DropCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el task.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            drop_handler: Handler para el comando de soltar item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.drop_handler = drop_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el drop de un item del inventario al suelo (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de dropear item sin estar logueado")
            return

        # Parsear datos: slot (u8) + quantity (u16)
        # slot=0 significa oro, slot=1-30 significa item del inventario
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        # Leer slot manualmente para permitir slot=0 (oro)
        slot = reader.read_byte()
        if slot is None:
            await self.message_sender.send_console_msg("Datos inválidos: slot no recibido")
            return

        # Validar rango: 0 para oro, 1-max para items
        max_slots = ConfigManager.as_int(config.get("game.inventory.max_slots", 30))
        if slot > max_slots:
            await self.message_sender.send_console_msg(f"Slot inválido: {slot}")
            return

        quantity = validator.read_quantity(min_qty=1, max_qty=10000)

        if validator.has_errors() or quantity is None:
            error_msg = (
                validator.get_error_message() if validator.has_errors() else "Datos inválidos"
            )
            await self.message_sender.send_console_msg(error_msg)
            return

        # Validar que tenemos el handler
        if not self.drop_handler:
            logger.error("DropCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = DropCommand(user_id=user_id, slot=slot, quantity=quantity)

        # Delegar al handler (separación de responsabilidades)
        result = await self.drop_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Soltar item falló: %s", result.error_message or "Error desconocido")
