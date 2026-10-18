"""Apilamiento atómico sobre el mismo recurso que utilizan banco y comercio."""

from enum import IntEnum
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager
from src.utils.inventory_atomic import change_inventory

if TYPE_CHECKING:
    from src.utils.inventory_storage import InventoryStorage


class InventoryStackingStrategy:
    """Planea cantidades completas sin writes parciales ni actualizaciones perdidas."""

    def __init__(self, storage: InventoryStorage, max_stack: int = 20) -> None:
        """Conserva almacenamiento y límite de cada stack."""
        self.storage = storage
        self.max_stack = max_stack

    async def add_item(self, user_id: int, item_id: int, quantity: int) -> list[tuple[int, int]]:
        """Agrega la cantidad completa o conserva todo el inventario.

        Returns:
            Slots modificados y sus cantidades confirmadas, o lista vacía si no entra.
        """
        if isinstance(item_id, IntEnum):
            item_id = int(item_id)
        if type(quantity) is not int or type(item_id) is not int or quantity < 1 or item_id < 1:
            return []
        result = await change_inventory(
            self.storage.redis_client.redis,
            user_id,
            "add",
            (item_id, quantity),
            ConfigManager.as_int(self.storage.MAX_SLOTS),
            self.max_stack,
        )
        return (
            [(slot, amount) for slot, _item, amount in result.get("slots", [])]
            if result["applied"]
            else []
        )

    async def remove_item(self, user_id: int, slot: int, quantity: int) -> bool:
        """Debita condicionalmente de un slot observado con WATCH.

        Returns:
            Si pudo retirarse la cantidad completa sin modificar equipo activo.
        """
        if type(quantity) is not int or type(slot) is not int or quantity < 1:
            return False
        result = await change_inventory(
            self.storage.redis_client.redis,
            user_id,
            "remove",
            (slot, quantity),
            ConfigManager.as_int(self.storage.MAX_SLOTS),
            self.max_stack,
        )
        return bool(result["applied"])

    async def remove_item_by_id(self, user_id: int, item_id: int, quantity: int) -> bool:
        """Retira una cantidad repartida entre slots sin debitar parcialmente.

        Returns:
            Éxito de la cantidad completa.
        """
        if isinstance(item_id, IntEnum):
            item_id = int(item_id)
        if type(quantity) is not int or type(item_id) is not int:
            return False
        if quantity < 1:
            return quantity == 0
        result = await change_inventory(
            self.storage.redis_client.redis,
            user_id,
            "remove_by_id",
            (item_id, quantity),
            ConfigManager.as_int(self.storage.MAX_SLOTS),
            self.max_stack,
        )
        return bool(result["applied"])
