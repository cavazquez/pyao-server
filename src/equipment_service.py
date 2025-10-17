"""Servicio para gestionar el equipamiento de items."""

import logging
from typing import TYPE_CHECKING

from src.equipment_slot import EquipmentSlot
from src.items_catalog import get_item

if TYPE_CHECKING:
    from src.equipment_repository import EquipmentRepository
    from src.inventory_repository import InventoryRepository
    from src.message_sender import MessageSender

logger = logging.getLogger(__name__)


class EquipmentService:
    """Servicio para gestionar equipamiento de items."""

    def __init__(
        self,
        equipment_repo: EquipmentRepository,
        inventory_repo: InventoryRepository,
    ) -> None:
        """Inicializa el servicio de equipamiento.

        Args:
            equipment_repo: Repositorio de equipamiento.
            inventory_repo: Repositorio de inventario.
        """
        self.equipment_repo = equipment_repo
        self.inventory_repo = inventory_repo

    async def toggle_equip_item(  # noqa: PLR0911
        self, user_id: int, inventory_slot: int, message_sender: MessageSender
    ) -> bool:
        """Equipa o desequipa un item del inventario.

        Si el item ya está equipado, lo desequipa.
        Si no está equipado, lo equipa (desequipando el item anterior en ese slot si existe).

        Args:
            user_id: ID del usuario.
            inventory_slot: Slot del inventario.
            message_sender: Para enviar mensajes al cliente.

        Returns:
            True si la operación fue exitosa, False en caso contrario.
        """
        # Obtener el item del inventario
        inventory = await self.inventory_repo.get_inventory(user_id)
        slot_key = f"slot_{inventory_slot}"
        slot_value = inventory.get(slot_key, "")

        if not slot_value or not isinstance(slot_value, str):
            await message_sender.send_console_msg("No hay item en ese slot.")
            return False

        try:
            item_id_str, _ = slot_value.split(":")
            item_id = int(item_id_str)
        except (ValueError, AttributeError):
            logger.exception("Formato de slot inválido: %s", slot_value)
            return False

        # Obtener información del item
        item = get_item(item_id)
        if not item:
            logger.error("Item %d no encontrado en catálogo", item_id)
            return False

        # Verificar si el item es equipable y determinar slot
        if not item.equippable:
            await message_sender.send_console_msg(f"{item.name} no se puede equipar.")
            return False

        equipment_slot = EquipmentSlot.from_item_type(item.item_type.value)
        if not equipment_slot:
            logger.error("No se pudo determinar slot de equipamiento para %s", item.item_type)
            return False

        # Verificar si el item ya está equipado
        equipped_slot = await self.equipment_repo.is_slot_equipped(user_id, inventory_slot)

        if equipped_slot:
            # Desequipar
            success = await self.equipment_repo.unequip_item(user_id, equipped_slot)
            if success:
                await message_sender.send_console_msg(f"Has desequipado {item.name}.")
                logger.info(
                    "user_id %d desequipó %s del slot %s",
                    user_id,
                    item.name,
                    equipped_slot.value,
                )
                return True
            return False
        # Equipar
        # Primero verificar si ya hay algo equipado en ese slot
        currently_equipped_inv_slot = await self.equipment_repo.get_equipped_slot(
            user_id, equipment_slot
        )

        if currently_equipped_inv_slot:
            # Desequipar el item anterior
            await self.equipment_repo.unequip_item(user_id, equipment_slot)
            logger.debug(
                "user_id %d desequipó item del slot %s para equipar nuevo item",
                user_id,
                equipment_slot.value,
            )

        # Equipar el nuevo item
        success = await self.equipment_repo.equip_item(user_id, equipment_slot, inventory_slot)
        if success:
            await message_sender.send_console_msg(f"Has equipado {item.name}.")
            logger.info(
                "user_id %d equipó %s en slot %s (inventory_slot=%d)",
                user_id,
                item.name,
                equipment_slot.value,
                inventory_slot,
            )
            return True

        return False

    async def get_equipped_items(self, user_id: int) -> dict[int, bool]:
        """Obtiene un diccionario de slots del inventario que están equipados.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con inventory_slot -> True para items equipados.
        """
        equipment = await self.equipment_repo.get_all_equipment(user_id)
        equipped_slots = {}
        for inv_slot in equipment.values():
            equipped_slots[inv_slot] = True
        return equipped_slots
