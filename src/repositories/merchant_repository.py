"""Repositorio para gestionar inventarios de mercaderes en Redis."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class MerchantItem:
    """Representa un item en el inventario de un mercader."""

    slot: int
    item_id: int
    quantity: int


class MerchantRepository:
    """Gestiona los inventarios de mercaderes en Redis."""

    MAX_SLOTS = 20  # Número máximo de slots de inventario del mercader

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio de mercaderes.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client

    async def get_inventory(self, npc_id: int) -> dict[str, str | int]:
        """Obtiene el inventario completo de un mercader.

        Args:
            npc_id: ID del NPC mercader.

        Returns:
            Diccionario con los slots del inventario.
            Formato: {"slot_1": "item_id:quantity", "slot_2": "", ...}
        """
        key = RedisKeys.merchant_inventory(npc_id)
        inventory = await self.redis_client.redis.hgetall(key)  # type: ignore[misc]

        # Si no existe, retornar inventario vacío
        if not inventory:
            logger.warning("Mercader %d no tiene inventario configurado", npc_id)
            return {}

        return inventory  # type: ignore[no-any-return]

    async def get_item(self, npc_id: int, slot: int) -> MerchantItem | None:
        """Obtiene un item específico del inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            slot: Número de slot (1-20).

        Returns:
            MerchantItem o None si el slot está vacío.
        """
        if slot < 1 or slot > self.MAX_SLOTS:
            logger.warning("Slot inválido: %d", slot)
            return None

        key = RedisKeys.merchant_inventory(npc_id)
        slot_key = f"slot_{slot}"
        value = await self.redis_client.redis.hget(key, slot_key)  # type: ignore[misc]

        if not value:
            return None

        # Parsear "item_id:quantity"
        try:
            item_id_str, quantity_str = value.split(":")
            return MerchantItem(
                slot=slot,
                item_id=int(item_id_str),
                quantity=int(quantity_str),
            )
        except (ValueError, AttributeError):
            logger.exception("Error parseando slot %d del mercader %d", slot, npc_id)
            return None

    async def get_all_items(self, npc_id: int) -> list[MerchantItem]:
        """Obtiene todos los items del inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.

        Returns:
            Lista de MerchantItem con todos los items disponibles.
        """
        inventory = await self.get_inventory(npc_id)
        items: list[MerchantItem] = []

        for slot_key, value in inventory.items():
            if not value:
                continue

            # Extraer número de slot
            try:
                slot_num = int(str(slot_key).split("_")[1])
            except (IndexError, ValueError):
                continue

            # Parsear item
            try:
                item_id_str, quantity_str = str(value).split(":")
                items.append(
                    MerchantItem(
                        slot=slot_num,
                        item_id=int(item_id_str),
                        quantity=int(quantity_str),
                    )
                )
            except (ValueError, AttributeError):
                logger.exception("Error parseando slot %s del mercader %d", slot_key, npc_id)
                continue

        # Ordenar por slot
        items.sort(key=lambda x: x.slot)
        return items

    async def add_item(self, npc_id: int, item_id: int, quantity: int) -> bool:
        """Agrega items al inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            item_id: ID del item a agregar.
            quantity: Cantidad a agregar.

        Returns:
            True si se agregó exitosamente, False si no hay espacio.
        """
        # Buscar si ya existe el item
        items = await self.get_all_items(npc_id)

        for item in items:
            if item.item_id == item_id:
                # Actualizar cantidad
                new_quantity = item.quantity + quantity
                await self._update_slot(npc_id, item.slot, item_id, new_quantity)
                logger.info(
                    "Mercader %d: Actualizado slot %d con %dx item %d",
                    npc_id,
                    item.slot,
                    new_quantity,
                    item_id,
                )
                return True

        # Buscar slot vacío
        for slot in range(1, self.MAX_SLOTS + 1):
            existing_item = await self.get_item(npc_id, slot)
            if not existing_item:
                await self._update_slot(npc_id, slot, item_id, quantity)
                logger.info(
                    "Mercader %d: Agregado %dx item %d en slot %d",
                    npc_id,
                    quantity,
                    item_id,
                    slot,
                )
                return True

        logger.warning("Mercader %d: Inventario lleno, no se pudo agregar item %d", npc_id, item_id)
        return False

    async def remove_item(self, npc_id: int, slot: int, quantity: int) -> bool:
        """Remueve items del inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            slot: Número de slot (1-20).
            quantity: Cantidad a remover.

        Returns:
            True si se removió exitosamente, False en caso contrario.
        """
        item = await self.get_item(npc_id, slot)
        if not item:
            logger.warning("Mercader %d: Slot %d está vacío", npc_id, slot)
            return False

        if item.quantity < quantity:
            logger.warning(
                "Mercader %d: Slot %d no tiene suficiente cantidad (%d < %d)",
                npc_id,
                slot,
                item.quantity,
                quantity,
            )
            return False

        new_quantity = item.quantity - quantity

        if new_quantity == 0:
            # Vaciar slot
            await self._clear_slot(npc_id, slot)
            logger.info("Mercader %d: Slot %d vaciado", npc_id, slot)
        else:
            # Actualizar cantidad
            await self._update_slot(npc_id, slot, item.item_id, new_quantity)
            logger.info(
                "Mercader %d: Slot %d actualizado a %d items",
                npc_id,
                slot,
                new_quantity,
            )

        return True

    async def initialize_inventory(
        self,
        npc_id: int,
        items: list[tuple[int, int]],
    ) -> None:
        """Inicializa el inventario de un mercader con items.

        Args:
            npc_id: ID del NPC mercader.
            items: Lista de tuplas (item_id, quantity).
        """
        key = RedisKeys.merchant_inventory(npc_id)

        # Crear inventario vacío
        inventory_data = {f"slot_{i}": "" for i in range(1, self.MAX_SLOTS + 1)}

        # Agregar items
        for slot, (item_id, quantity) in enumerate(items, start=1):
            if slot > self.MAX_SLOTS:
                break
            inventory_data[f"slot_{slot}"] = f"{item_id}:{quantity}"

        await self.redis_client.redis.hset(key, mapping=inventory_data)  # type: ignore[misc]
        logger.info("Inventario inicializado para mercader %d con %d items", npc_id, len(items))

    async def _update_slot(
        self,
        npc_id: int,
        slot: int,
        item_id: int,
        quantity: int,
    ) -> None:
        """Actualiza un slot del inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            slot: Número de slot (1-20).
            item_id: ID del item.
            quantity: Cantidad.
        """
        key = RedisKeys.merchant_inventory(npc_id)
        slot_key = f"slot_{slot}"
        value = f"{item_id}:{quantity}"
        await self.redis_client.redis.hset(key, slot_key, value)  # type: ignore[misc]

    async def _clear_slot(self, npc_id: int, slot: int) -> None:
        """Vacía un slot del inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            slot: Número de slot (1-20).
        """
        key = RedisKeys.merchant_inventory(npc_id)
        slot_key = f"slot_{slot}"
        await self.redis_client.redis.hset(key, slot_key, "")  # type: ignore[misc]
