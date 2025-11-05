"""Repositorio base para entidades que usan slots (inventarios, bancos, etc)."""

import logging
from typing import TYPE_CHECKING

from src.utils.item_slot_parser import ItemSlotParser, ParsedItem

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class BaseSlotRepository:
    """Clase base para repositorios que manejan slots de items.

    Proporciona métodos comunes para actualizar, limpiar y apilar items
    en estructuras de slots almacenadas en Redis.
    """

    MAX_SLOTS = 20

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio base.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client

    async def _update_slot(
        self,
        key: str,
        slot: int,
        item_id: int,
        quantity: int,
    ) -> None:
        """Actualiza un slot con un item.

        Args:
            key: Key de Redis para el hash.
            slot: Número de slot.
            item_id: ID del item.
            quantity: Cantidad del item.
        """
        slot_key = f"slot_{slot}"
        value = ItemSlotParser.format_value(item_id, quantity)
        await self.redis_client.redis.hset(key, slot_key, value)  # type: ignore[misc]

    async def _clear_slot(self, key: str, slot: int) -> None:
        """Vacía un slot.

        Args:
            key: Key de Redis para el hash.
            slot: Número de slot.
        """
        slot_key = f"slot_{slot}"
        await self.redis_client.redis.hset(key, slot_key, "")  # type: ignore[misc]

    async def _get_slot_value(self, key: str, slot: int) -> ParsedItem | None:
        """Obtiene el valor parseado de un slot.

        Args:
            key: Key de Redis para el hash.
            slot: Número de slot.

        Returns:
            ParsedItem o None si el slot está vacío o hay error.
        """
        slot_key = f"slot_{slot}"
        value = await self.redis_client.redis.hget(key, slot_key)  # type: ignore[misc]
        return ItemSlotParser.parse(value)

    async def _get_all_slots(self, key: str) -> dict[str, str]:
        """Obtiene todos los slots de un hash.

        Args:
            key: Key de Redis para el hash.

        Returns:
            Diccionario con todos los slots.
        """
        slots = await self.redis_client.redis.hgetall(key)  # type: ignore[misc]
        return slots or {}

    async def _initialize_empty_slots(self, key: str) -> None:
        """Inicializa todos los slots vacíos.

        Args:
            key: Key de Redis para el hash.
        """
        data = {f"slot_{i}": "" for i in range(1, self.MAX_SLOTS + 1)}
        await self.redis_client.redis.hset(key, mapping=data)  # type: ignore[misc]

    async def _find_stackable_slot(
        self,
        key: str,
        item_id: int,
    ) -> tuple[int, int] | None:
        """Busca un slot con el mismo item para apilar.

        Args:
            key: Key de Redis para el hash.
            item_id: ID del item a buscar.

        Returns:
            Tupla (slot_number, current_quantity) o None si no se encuentra.
        """
        all_slots = await self._get_all_slots(key)

        for slot in range(1, self.MAX_SLOTS + 1):
            slot_key = f"slot_{slot}"
            value = all_slots.get(slot_key, "")

            if value:
                parsed = ItemSlotParser.parse(value)
                if parsed and parsed.item_id == item_id:
                    return (slot, parsed.quantity)

        return None

    async def _find_empty_slot(self, key: str) -> int | None:
        """Busca el primer slot vacío.

        Args:
            key: Key de Redis para el hash.

        Returns:
            Número de slot vacío o None si no hay espacio.
        """
        all_slots = await self._get_all_slots(key)

        for slot in range(1, self.MAX_SLOTS + 1):
            slot_key = f"slot_{slot}"
            value = all_slots.get(slot_key, "")

            if not value:
                return slot

        return None

    async def _stack_or_add_item(
        self,
        key: str,
        item_id: int,
        quantity: int,
    ) -> int | None:
        """Intenta apilar un item o agregarlo en un slot vacío.

        Args:
            key: Key de Redis para el hash.
            item_id: ID del item.
            quantity: Cantidad a agregar.

        Returns:
            Número de slot donde se agregó, o None si no hay espacio.
        """
        # Intentar apilar con item existente
        stackable = await self._find_stackable_slot(key, item_id)
        if stackable:
            slot, current_qty = stackable
            new_quantity = current_qty + quantity
            await self._update_slot(key, slot, item_id, new_quantity)
            logger.debug("Item %d apilado en slot %d (cantidad: %d)", item_id, slot, new_quantity)
            return slot

        # Buscar slot vacío
        empty_slot = await self._find_empty_slot(key)
        if empty_slot:
            await self._update_slot(key, empty_slot, item_id, quantity)
            logger.debug(
                "Item %d agregado en slot %d (cantidad: %d)", item_id, empty_slot, quantity
            )
            return empty_slot

        return None
