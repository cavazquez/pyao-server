"""Tarea para equipar/desequipar items."""

import logging
from typing import TYPE_CHECKING

from src.equipment_service import EquipmentService
from src.inventory_repository import InventoryRepository
from src.packet_data import EquipItemData
from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.player_service import PlayerService
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.equipment_repository import EquipmentRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskEquipItem(Task):
    """Maneja equipar/desequipar items del inventario."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        equipment_repo: EquipmentRepository | None = None,
    ) -> None:
        """Inicializa la tarea de equipar item.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
            equipment_repo: Repositorio de equipamiento.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data or {}
        self.equipment_repo = equipment_repo

    async def execute(self) -> None:
        """Ejecuta equipar/desequipar item."""
        # Parsear el packet: PacketID (1 byte) + Slot (1 byte)
        min_packet_size = 2
        if len(self.data) < min_packet_size:
            logger.warning("Packet EQUIP_ITEM inválido: tamaño incorrecto")
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de equipar item sin estar logueado")
            return

        # Verificar dependencias
        if not self.player_repo or not self.equipment_repo:
            logger.error("Dependencias no disponibles para equipar item")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        slot = validator.read_slot(min_slot=1, max_slot=20)

        if validator.has_errors() or slot is None:
            error_msg = validator.get_error_message() if validator.has_errors() else "Slot inválido"
            await self.message_sender.send_console_msg(error_msg)
            return

        # Crear dataclass con datos validados
        equip_data = EquipItemData(slot=slot)

        logger.info(
            "user_id %d intenta equipar/desequipar item en slot %d", user_id, equip_data.slot
        )

        try:
            # Crear servicio de equipamiento
            inventory_repo = InventoryRepository(self.player_repo.redis)
            equipment_service = EquipmentService(self.equipment_repo, inventory_repo)

            # Equipar o desequipar el item
            success = await equipment_service.toggle_equip_item(
                user_id, equip_data.slot, self.message_sender
            )

            if success:
                # Reenviar el inventario completo para actualizar el estado de equipamiento
                player_service = PlayerService(self.player_repo, self.message_sender)
                await player_service.send_inventory(user_id, self.equipment_repo)

        except Exception:
            logger.exception("Error procesando EQUIP_ITEM")
