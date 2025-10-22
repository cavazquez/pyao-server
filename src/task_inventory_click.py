"""Tarea para manejar clicks en el inventario."""

import logging
from typing import TYPE_CHECKING

from src.inventory_repository import InventoryRepository
from src.items_catalog import get_item
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.equipment_repository import EquipmentRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskInventoryClick(Task):
    """Maneja el click en un slot del inventario para mostrar información."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        equipment_repo: EquipmentRepository | None = None,
    ) -> None:
        """Inicializa la tarea de click en inventario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            slot: Slot del inventario (ya validado).
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
            equipment_repo: Repositorio de equipamiento.
        """
        super().__init__(data, message_sender)
        self.slot = slot
        self.player_repo = player_repo
        self.session_data = session_data or {}
        self.equipment_repo = equipment_repo

    async def execute(self) -> None:
        """Ejecuta el click en un slot del inventario.

        El slot ya fue validado por TaskFactory.
        """
        # Verificar que el jugador esté logueado
        if not self.session_data:
            logger.warning("session_data no disponible")
            return

        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de click en inventario sin estar logueado")
            return

        # Verificar que tengamos player_repo
        if not self.player_repo:
            logger.error("player_repo no disponible")
            return

        logger.info("user_id %d hace click en slot %d", user_id, self.slot)

        try:
            # Obtener el inventario
            inventory_repo = InventoryRepository(self.player_repo.redis)
            slot_data = await inventory_repo.get_slot(user_id, self.slot)

            if not slot_data:
                # Slot vacío - enviar actualización con slot vacío
                await self.message_sender.send_change_inventory_slot(
                    slot=self.slot,
                    item_id=0,
                    name="",
                    amount=0,
                    equipped=False,
                    grh_id=0,
                    item_type=0,
                    max_hit=0,
                    min_hit=0,
                    max_def=0,
                    min_def=0,
                    sale_price=0.0,
                )
                return

            item_id, quantity = slot_data

            # Obtener el item del catálogo
            item = get_item(item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", item_id)
                await self.message_sender.send_console_msg("Item no válido.")
                return

            # Verificar si el item está equipado
            is_equipped = False
            if self.equipment_repo:
                equipped_slot = await self.equipment_repo.is_slot_equipped(user_id, self.slot)
                is_equipped = equipped_slot is not None

            # Enviar información del slot actualizada
            await self.message_sender.send_change_inventory_slot(
                slot=self.slot,
                item_id=item.item_id,
                name=item.name,
                amount=quantity,
                equipped=is_equipped,
                grh_id=item.graphic_id,
                item_type=item.item_type.to_client_type(),
                max_hit=item.max_damage or 0,
                min_hit=item.min_damage or 0,
                max_def=item.defense or 0,
                min_def=item.defense or 0,
                sale_price=float(item.value),
            )

            logger.info(
                "user_id %d - Slot %d: %s x%d (GrhIndex: %d)",
                user_id,
                self.slot,
                item.name,
                quantity,
                item.graphic_id,
            )

            # Detectar herramientas equipadas y cambiar cursor al modo de trabajo
            # Solo enviar si ESTÁ equipada (lista para usar)
            work_tools = {
                561: 1,  # Hacha de Leñador → Talar
                562: 2,  # Piquete de Minero → Minería
                563: 3,  # Caña de pescar → Pesca
            }

            if item_id in work_tools and is_equipped:
                skill_type = work_tools[item_id]
                await self.message_sender.send_work_request_target(skill_type)
                logger.info("Herramienta equipada - Cursor cambiado a modo trabajo: skill_type=%d", skill_type)

        except Exception:
            logger.exception("Error procesando INVENTORY_CLICK")
