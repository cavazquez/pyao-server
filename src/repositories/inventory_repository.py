"""Repositorio para gestionar inventarios de jugadores en Redis.

Este repositorio ahora actúa como una fachada que coordina
los componentes más simples: InventoryStorage y InventoryStackingStrategy.
"""

import logging
from dataclasses import dataclass

from src.config.config_manager import ConfigManager, config_manager
from src.utils.inventory_slot import InventorySlot
from src.utils.inventory_stacking_strategy import InventoryStackingStrategy
from src.utils.inventory_storage import InventoryStorage
from src.utils.redis_client import RedisClient  # noqa: TC001
from src.utils.redis_config import RedisKeys

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SwapSlotsResult:
    """Resultado de intercambiar dos slots del inventario."""

    success: bool
    old_slot: int
    new_slot: int
    old_slot_data: tuple[int, int] | None
    new_slot_data: tuple[int, int] | None
    reason: str | None = None


class InventoryRepository:
    """Gestiona el inventario de jugadores en Redis.

    Esta clase actúa como fachada que coordina InventoryStorage
    y InventoryStackingStrategy para proporcionar una API simple.
    """

    MAX_SLOTS = config_manager.get(
        "game.inventory.max_slots", 30
    )  # Número máximo de slots de inventario

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
        for i in range(1, ConfigManager.as_int(self.MAX_SLOTS) + 1):
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

    async def remove_item_by_item_id(self, user_id: int, item_id: int, quantity: int) -> bool:
        """Remueve cantidad de un item buscando por item_id.

        Args:
            user_id: ID del jugador.
            item_id: ID del item a remover.
            quantity: Cantidad total a remover.

        Returns:
            True si se removió la cantidad solicitada.
        """
        if quantity <= 0:
            return True

        slots = await self.get_inventory_slots(user_id)
        remaining = quantity

        for slot_number, slot in slots.items():
            if slot.item_id != item_id or remaining <= 0:
                continue

            removable = min(slot.quantity, remaining)
            success = await self.remove_item(user_id, slot_number, removable)
            if not success:
                return False
            remaining -= removable

            if remaining == 0:
                return True

        return remaining == 0

    async def has_space(self, user_id: int) -> bool:
        """Verifica si hay espacio en el inventario.

        Args:
            user_id: ID del jugador.

        Returns:
            True si hay al menos un slot vacío.
        """
        return await self.storage.has_space(user_id)

    async def swap_slots(
        self, user_id: int, old_slot: int, new_slot: int
    ) -> SwapSlotsResult | None:
        """Intercambia el contenido de dos slots del inventario.

        Args:
            user_id: ID del jugador.
            old_slot: Slot de origen (1-based).
            new_slot: Slot de destino (1-based).

        Returns:
            SwapSlotsResult con información del intercambio, o None si Redis no disponible.
        """
        max_slots = ConfigManager.as_int(self.MAX_SLOTS)

        if not (1 <= old_slot <= max_slots and 1 <= new_slot <= max_slots):
            reasons = []
            if not 1 <= old_slot <= max_slots:
                reasons.append(f"old_slot={old_slot}")
            if not 1 <= new_slot <= max_slots:
                reasons.append(f"new_slot={new_slot}")
            return SwapSlotsResult(
                success=False,
                old_slot=old_slot,
                new_slot=new_slot,
                old_slot_data=None,
                new_slot_data=None,
                reason=f"Slot fuera de rango: {', '.join(reasons)}",
            )

        key = RedisKeys.player_inventory(user_id)

        # Leer ambos slots en un pipeline
        pipe = self.redis_client.redis.pipeline()
        pipe.hget(key, f"slot_{old_slot}")
        pipe.hget(key, f"slot_{new_slot}")
        old_value, new_value = await pipe.execute()

        # Parsear valores actuales
        old_slot_data = None
        if old_value:
            parsed = InventorySlot.parse(old_value)
            if parsed and not parsed.is_empty():
                old_slot_data = (parsed.item_id, parsed.quantity)

        new_slot_data = None
        if new_value:
            parsed = InventorySlot.parse(new_value)
            if parsed and not parsed.is_empty():
                new_slot_data = (parsed.item_id, parsed.quantity)

        # Intercambiar valores en un pipeline transaccional
        pipe = self.redis_client.redis.pipeline(transaction=True)
        if new_value:
            pipe.hset(key, f"slot_{old_slot}", new_value)
        else:
            pipe.hdel(key, f"slot_{old_slot}")

        if old_value:
            pipe.hset(key, f"slot_{new_slot}", old_value)
        else:
            pipe.hdel(key, f"slot_{new_slot}")

        await pipe.execute()

        logger.info(
            "Swap slots user_id=%d: slot %s <-> slot %s",
            user_id,
            old_slot,
            new_slot,
        )

        return SwapSlotsResult(
            success=True,
            old_slot=old_slot,
            new_slot=new_slot,
            old_slot_data=new_slot_data,
            new_slot_data=old_slot_data,
        )
