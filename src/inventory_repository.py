"""Repositorio para gestionar inventarios de jugadores en Redis."""

import logging
from typing import TYPE_CHECKING

from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class InventoryRepository:
    """Gestiona el inventario de jugadores en Redis."""

    MAX_SLOTS = 20  # Número máximo de slots de inventario

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio de inventario.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client

    async def get_inventory(self, user_id: int) -> dict[str, str | int]:
        """Obtiene el inventario completo de un jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Diccionario con los slots del inventario.
            Formato: {"slot_1": "item_id:quantity", "slot_2": "", ...}
        """
        key = RedisKeys.player_inventory(user_id)
        inventory = await self.redis_client.redis.hgetall(key)  # type: ignore[misc]

        # Si no existe, crear inventario vacío
        if not inventory:
            inventory = await self._create_empty_inventory(user_id)

        return inventory  # type: ignore[no-any-return]

    async def _create_empty_inventory(self, user_id: int) -> dict[str, str]:
        """Crea un inventario vacío para un jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Diccionario con slots vacíos.
        """
        key = RedisKeys.player_inventory(user_id)
        empty_inventory = {f"slot_{i}": "" for i in range(1, self.MAX_SLOTS + 1)}

        await self.redis_client.redis.hset(key, mapping=empty_inventory)  # type: ignore[misc]
        logger.info("Inventario vacío creado para user_id %d", user_id)

        return empty_inventory

    async def get_slot(self, user_id: int, slot: int) -> tuple[int, int] | None:
        """Obtiene el contenido de un slot específico.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).

        Returns:
            Tupla (item_id, quantity) o None si está vacío.
        """
        if slot < 1 or slot > self.MAX_SLOTS:
            logger.warning("Slot inválido: %d", slot)
            return None

        key = RedisKeys.player_inventory(user_id)
        slot_key = f"slot_{slot}"
        value = await self.redis_client.redis.hget(key, slot_key)  # type: ignore[misc]

        if not value:
            return None

        try:
            item_id, quantity = value.split(":")
            return int(item_id), int(quantity)
        except (ValueError, AttributeError):
            logger.warning("Formato inválido en slot %d para user_id %d: %s", slot, user_id, value)
            return None

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
        if slot < 1 or slot > self.MAX_SLOTS:
            logger.warning("Slot inválido: %d", slot)
            return False

        if quantity < 0:
            logger.warning("Cantidad inválida: %d", quantity)
            return False

        key = RedisKeys.player_inventory(user_id)
        slot_key = f"slot_{slot}"

        if quantity == 0:
            # Vaciar el slot
            await self.redis_client.redis.hset(key, slot_key, "")  # type: ignore[misc]
        else:
            value = f"{item_id}:{quantity}"
            await self.redis_client.redis.hset(key, slot_key, value)  # type: ignore[misc]

        logger.debug(
            "Slot %d actualizado para user_id %d: item_id=%d, quantity=%d",
            slot,
            user_id,
            item_id,
            quantity,
        )
        return True

    async def clear_slot(self, user_id: int, slot: int) -> bool:
        """Vacía un slot del inventario.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).

        Returns:
            True si se vació correctamente.
        """
        return await self.set_slot(user_id, slot, 0, 0)

    async def add_item(
        self, user_id: int, item_id: int, quantity: int = 1, max_stack: int = 20
    ) -> list[tuple[int, int]]:
        """Agrega un item al inventario.

        Args:
            user_id: ID del jugador.
            item_id: ID del item a agregar.
            quantity: Cantidad a agregar.
            max_stack: Cantidad máxima por stack.

        Returns:
            Lista de tuplas (slot, cantidad_en_slot) de los slots modificados.
            Lista vacía si no hay espacio.
        """
        inventory = await self.get_inventory(user_id)
        remaining_quantity = quantity
        modified_slots: list[tuple[int, int]] = []

        # Primero intentar apilar en slots existentes del mismo item
        for i in range(1, self.MAX_SLOTS + 1):
            if remaining_quantity <= 0:
                break

            slot_key = f"slot_{i}"
            slot_value = inventory.get(slot_key, "")

            if slot_value and isinstance(slot_value, str):
                parts = slot_value.split(":")
                if len(parts) == 2:  # noqa: PLR2004
                    existing_item_id = int(parts[0])
                    existing_quantity = int(parts[1])

                    # Si es el mismo item y no está lleno el stack
                    if existing_item_id == item_id and existing_quantity < max_stack:
                        # Calcular cuánto podemos agregar a este stack
                        space_in_stack = max_stack - existing_quantity
                        to_add = min(remaining_quantity, space_in_stack)

                        # Actualizar el slot
                        new_quantity = existing_quantity + to_add
                        await self.set_slot(user_id, i, item_id, new_quantity)

                        remaining_quantity -= to_add
                        modified_slots.append((i, new_quantity))

        # Si todavía queda cantidad, buscar slots vacíos
        while remaining_quantity > 0:
            empty_slot = None
            for i in range(1, self.MAX_SLOTS + 1):
                slot_key = f"slot_{i}"
                if not inventory.get(slot_key, ""):
                    empty_slot = i
                    break

            if empty_slot is None:
                logger.warning("No hay espacio en inventario para user_id %d", user_id)
                return []

            # Agregar lo que quepa en este slot
            to_add = min(remaining_quantity, max_stack)
            await self.set_slot(user_id, empty_slot, item_id, to_add)
            remaining_quantity -= to_add

            # Actualizar inventory local para el siguiente loop
            inventory[f"slot_{empty_slot}"] = f"{item_id}:{to_add}"
            modified_slots.append((empty_slot, to_add))

        return modified_slots

    async def remove_item(self, user_id: int, slot: int, quantity: int = 1) -> bool:
        """Remueve cantidad de un item de un slot.

        Args:
            user_id: ID del jugador.
            slot: Número de slot.
            quantity: Cantidad a remover.

        Returns:
            True si se removió correctamente.
        """
        slot_data = await self.get_slot(user_id, slot)
        if not slot_data:
            return False

        item_id, current_quantity = slot_data

        if current_quantity < quantity:
            logger.warning("No hay suficiente cantidad en slot %d", slot)
            return False

        new_quantity = current_quantity - quantity

        if new_quantity <= 0:
            await self.clear_slot(user_id, slot)
        else:
            await self.set_slot(user_id, slot, item_id, new_quantity)

        return True

    async def has_space(self, user_id: int) -> bool:
        """Verifica si hay espacio en el inventario.

        Args:
            user_id: ID del jugador.

        Returns:
            True si hay al menos un slot vacío.
        """
        inventory = await self.get_inventory(user_id)

        for i in range(1, self.MAX_SLOTS + 1):
            slot_key = f"slot_{i}"
            if not inventory.get(slot_key, ""):
                return True

        return False
