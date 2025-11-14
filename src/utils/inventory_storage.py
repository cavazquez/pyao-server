"""Capa de almacenamiento para inventarios en Redis."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class InventoryStorage:
    """Gestiona el almacenamiento de inventarios en Redis.

    Esta clase es responsable únicamente de la persistencia,
    sin lógica de negocio de inventario.
    """

    MAX_SLOTS = config_manager.get("game.max_inventory_slots", 30)

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el storage de inventario.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client

    async def get_slot(self, user_id: int, slot: int) -> InventorySlot | None:
        """Obtiene el contenido de un slot específico.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).

        Returns:
            InventorySlot o None si está vacío o inválido.
        """
        if not self._is_valid_slot(slot):
            logger.warning("Slot inválido: %d", slot)
            return None

        key = RedisKeys.player_inventory(user_id)
        slot_key = f"slot_{slot}"
        value = await self.redis_client.redis.hget(key, slot_key)  # type: ignore[misc]

        return InventorySlot.parse(value) if value else None

    async def set_slot(self, user_id: int, slot: int, inventory_slot: InventorySlot | None) -> bool:
        """Establece el contenido de un slot.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).
            inventory_slot: InventorySlot a guardar, o None para vaciar.

        Returns:
            True si se actualizó correctamente.
        """
        if not self._is_valid_slot(slot):
            logger.warning("Slot inválido: %d", slot)
            return False

        key = RedisKeys.player_inventory(user_id)
        slot_key = f"slot_{slot}"

        if inventory_slot is None or inventory_slot.is_empty():
            # Vaciar el slot
            await self.redis_client.redis.hset(key, slot_key, "")  # type: ignore[misc]
            logger.debug("Slot %d vaciado para user_id %d", slot, user_id)
        else:
            value = inventory_slot.to_string()
            await self.redis_client.redis.hset(key, slot_key, value)  # type: ignore[misc]
            logger.debug(
                "Slot %d actualizado para user_id %d: %s",
                slot,
                user_id,
                value,
            )

        return True

    async def get_all_slots(self, user_id: int) -> dict[int, InventorySlot]:
        """Obtiene todos los slots del inventario.

        Args:
            user_id: ID del jugador.

        Returns:
            Diccionario {slot_number: InventorySlot} con solo los slots ocupados.
        """
        key = RedisKeys.player_inventory(user_id)
        inventory = await self.redis_client.redis.hgetall(key)  # type: ignore[misc]

        # Si no existe, crear inventario vacío
        if not inventory:
            await self._create_empty_inventory(user_id)
            return {}

        # Parsear slots
        slots: dict[int, InventorySlot] = {}
        for slot_num in range(1, ConfigManager.as_int(self.MAX_SLOTS) + 1):
            slot_key = f"slot_{slot_num}"
            value = inventory.get(slot_key)

            if value:
                parsed_slot = InventorySlot.parse(value)
                if parsed_slot:
                    slots[slot_num] = parsed_slot

        return slots

    async def clear_slot(self, user_id: int, slot: int) -> bool:
        """Vacía un slot del inventario.

        Args:
            user_id: ID del jugador.
            slot: Número de slot (1-20).

        Returns:
            True si se vació correctamente.
        """
        return await self.set_slot(user_id, slot, None)

    async def find_empty_slot(self, user_id: int) -> int | None:
        """Encuentra el primer slot vacío.

        Args:
            user_id: ID del jugador.

        Returns:
            Número de slot vacío o None si no hay espacio.
        """
        slots = await self.get_all_slots(user_id)

        for slot_num in range(1, ConfigManager.as_int(self.MAX_SLOTS) + 1):
            if slot_num not in slots:
                return slot_num

        return None

    async def has_space(self, user_id: int) -> bool:
        """Verifica si hay espacio en el inventario.

        Args:
            user_id: ID del jugador.

        Returns:
            True si hay al menos un slot vacío.
        """
        empty_slot = await self.find_empty_slot(user_id)
        return empty_slot is not None

    async def _create_empty_inventory(self, user_id: int) -> None:
        """Crea un inventario vacío para un jugador.

        Args:
            user_id: ID del jugador.
        """
        key = RedisKeys.player_inventory(user_id)
        empty_inventory = {
            f"slot_{i}": "" for i in range(1, ConfigManager.as_int(self.MAX_SLOTS) + 1)
        }

        await self.redis_client.redis.hset(key, mapping=empty_inventory)  # type: ignore[misc]
        logger.info("Inventario vacío creado para user_id %d", user_id)

    def _is_valid_slot(self, slot: int) -> bool:
        """Valida que el número de slot sea válido.

        Args:
            slot: Número de slot.

        Returns:
            True si el slot está entre 1 y MAX_SLOTS.
        """
        return 1 <= slot <= ConfigManager.as_int(self.MAX_SLOTS)
