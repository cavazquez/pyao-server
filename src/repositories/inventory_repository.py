"""Repositorio para gestionar inventarios de jugadores en Redis.

Este repositorio ahora actúa como una fachada que coordina
los componentes más simples: InventoryStorage y InventoryStackingStrategy.
"""

import logging

from src.config import config
from src.utils.inventory_slot import InventorySlot
from src.utils.inventory_stacking_strategy import InventoryStackingStrategy
from src.utils.inventory_storage import InventoryStorage
from src.utils.redis_client import RedisClient  # noqa: TC001

logger = logging.getLogger(__name__)


class InventoryRepository:
    """Gestiona el inventario de jugadores en Redis.

    Esta clase actúa como fachada que coordina InventoryStorage
    y InventoryStackingStrategy para proporcionar una API simple.
    """

    MAX_SLOTS = config.game.max_inventory_slots  # Número máximo de slots de inventario

    def __init__(self, redis_client: RedisClient, max_stack: int = 20) -> None:
        """Inicializa el repositorio de inventario.

        Args:
            redis_client: Cliente de Redis.
            max_stack: Cantidad máxima por stack (default: 20).
        """
        self.redis_client = redis_client
        self.storage = InventoryStorage(redis_client)
        self.stacking = InventoryStackingStrategy(self.storage, max_stack)

    async def get_inventory(self, user_id: int) -> dict[str, str]:
        """Obtiene el inventario completo de un jugador en formato legacy.

        Args:
            user_id: ID del jugador.

        Returns:
            Diccionario con formato legacy {"slot_1": "item_id:quantity", ...}.

        Note:
            Este método mantiene compatibilidad con código existente.
            Para nuevo código, usar get_inventory_slots().
        """
        slots = await self.storage.get_all_slots(user_id)

        # Convertir a formato legacy
        legacy_inventory: dict[str, str] = {}
        for i in range(1, self.MAX_SLOTS + 1):
            slot_key = f"slot_{i}"
            if i in slots:
                legacy_inventory[slot_key] = slots[i].to_string()
            else:
                legacy_inventory[slot_key] = ""

        return legacy_inventory

    async def get_inventory_slots(self, user_id: int) -> dict[int, InventorySlot]:
        """Obtiene el inventario completo de un jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Diccionario {slot_number: InventorySlot} con solo los slots ocupados.
        """
        return await self.storage.get_all_slots(user_id)

    async def get_slot(self, user_id: int, slot: int) -> tuple[int, int] | None:
        """Obtiene el contenido de un slot específico.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-max_inventory_slots).

        Returns:
            Tupla (item_id, quantity) o None si está vacío.
        """
        inventory_slot = await self.storage.get_slot(user_id, slot)

        if inventory_slot is None:
            return None

        return inventory_slot.item_id, inventory_slot.quantity

    async def set_slot(self, user_id: int, slot: int, item_id: int, quantity: int) -> bool:
        """Establece el contenido de un slot.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).
            item_id: ID del item.
            quantity: Cantidad del item.

        Returns:
            True si se actualizó correctamente.
        """
        if quantity < 0:
            logger.warning("Cantidad inválida: %d", quantity)
            return False

        if quantity == 0:
            return await self.storage.clear_slot(user_id, slot)

        inventory_slot = InventorySlot(item_id=item_id, quantity=quantity)
        return await self.storage.set_slot(user_id, slot, inventory_slot)

    async def clear_slot(self, user_id: int, slot: int) -> bool:
        """Vacía un slot del inventario.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).

        Returns:
            True si se vació correctamente.
        """
        return await self.storage.clear_slot(user_id, slot)

    async def add_item(
        self, user_id: int, item_id: int, quantity: int = 1
    ) -> list[tuple[int, int]]:
        """Agrega un item al inventario.

        Args:
            user_id: ID del jugador.
            item_id: ID del item a agregar.
            quantity: Cantidad a agregar.

        Returns:
            Lista de tuplas (slot, cantidad_en_slot) de los slots modificados.
            Lista vacía si no hay espacio.
        """
        return await self.stacking.add_item(user_id, item_id, quantity)

    async def remove_item(self, user_id: int, slot: int, quantity: int = 1) -> bool:
        """Remueve cantidad de un item de un slot.

        Args:
            user_id: ID del jugador.
            slot: Número de slot.
            quantity: Cantidad a remover.

        Returns:
            True si se removió correctamente.
        """
        return await self.stacking.remove_item(user_id, slot, quantity)

    async def has_space(self, user_id: int) -> bool:
        """Verifica si hay espacio en el inventario.

        Args:
            user_id: ID del jugador.

        Returns:
            True si hay al menos un slot vacío.
        """
        return await self.storage.has_space(user_id)
