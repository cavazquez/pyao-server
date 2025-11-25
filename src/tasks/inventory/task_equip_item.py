"""Tarea para equipar/desequipar items."""

import logging
from typing import TYPE_CHECKING

from src.commands.equip_item_command import EquipItemCommand
from src.config import config
from src.config.config_manager import ConfigManager
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task
from src.utils.packet_length_validator import PacketLengthValidator

if TYPE_CHECKING:
    from src.command_handlers.equip_item_handler import EquipItemCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskEquipItem(Task):
    """Maneja equipar/desequipar items del inventario (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        equip_item_handler: EquipItemCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de equipar item.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            equip_item_handler: Handler para el comando de equipar/desequipar item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.equip_item_handler = equip_item_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta equipar/desequipar item (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar longitud del packet usando PacketLengthValidator
        if not await PacketLengthValidator.validate_min_length(self.data, 19, self.message_sender):
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de equipar item sin estar logueado")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        slot = validator.read_slot(
            min_slot=1,
            max_slot=ConfigManager.as_int(config.get("game.inventory.max_slots", 30)),
        )

        if validator.has_errors() or slot is None:
            error_msg = validator.get_error_message() if validator.has_errors() else "Slot inválido"
            await self.message_sender.send_console_msg(error_msg)
            return

        # Validar que tenemos el handler
        if not self.equip_item_handler:
            logger.error("EquipItemCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = EquipItemCommand(user_id=user_id, slot=slot)

        # Delegar al handler (separación de responsabilidades)
        result = await self.equip_item_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Equipar/desequipar item falló: %s", result.error_message or "Error desconocido"
            )
