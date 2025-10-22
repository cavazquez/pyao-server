"""Estrategia para manejar el apilamiento de items en inventario."""

import logging
from typing import TYPE_CHECKING

from src.utils.inventory_slot import InventorySlot

if TYPE_CHECKING:
    from src.utils.inventory_storage import InventoryStorage

logger = logging.getLogger(__name__)


class InventoryStackingStrategy:
    """Maneja la lógica de apilamiento de items en el inventario.

    Esta clase implementa la estrategia de cómo agregar items al inventario:
    1. Primero intenta apilar en slots existentes del mismo item
    2. Luego busca slots vacíos para crear nuevos stacks
    """

    def __init__(self, storage: InventoryStorage, max_stack: int = 20) -> None:
        """Inicializa la estrategia de stacking.

        Args:
            storage: Storage de inventario.
            max_stack: Cantidad máxima por stack (default: 20).
        """
        self.storage = storage
        self.max_stack = max_stack

    async def add_item(self, user_id: int, item_id: int, quantity: int) -> list[tuple[int, int]]:
        """Agrega un item al inventario usando estrategia de stacking.

        Args:
            user_id: ID del jugador.
            item_id: ID del item a agregar.
            quantity: Cantidad a agregar.

        Returns:
            Lista de tuplas (slot, cantidad_en_slot) de los slots modificados.
            Lista vacía si no hay espacio suficiente.
        """
        if quantity <= 0:
            logger.warning("Cantidad inválida para agregar: %d", quantity)
            return []

        # Obtener todos los slots actuales
        slots = await self.storage.get_all_slots(user_id)
        remaining_quantity = quantity
        modified_slots: list[tuple[int, int]] = []

        # Fase 1: Intentar apilar en slots existentes del mismo item
        remaining_quantity, phase1_mods = await self._stack_in_existing_slots(
            user_id, item_id, remaining_quantity, slots
        )
        modified_slots.extend(phase1_mods)

        # Fase 2: Si todavía queda cantidad, usar slots vacíos
        if remaining_quantity > 0:
            phase2_success, phase2_mods = await self._fill_empty_slots(
                user_id, item_id, remaining_quantity
            )

            if not phase2_success:
                # No hay suficiente espacio
                logger.warning("No hay espacio suficiente en inventario para user_id %d", user_id)
                return []

            modified_slots.extend(phase2_mods)

        return modified_slots

    async def _stack_in_existing_slots(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
        slots: dict[int, InventorySlot],
    ) -> tuple[int, list[tuple[int, int]]]:
        """Intenta apilar en slots existentes del mismo item.

        Args:
            user_id: ID del jugador.
            item_id: ID del item.
            quantity: Cantidad a agregar.
            slots: Diccionario de slots actuales.

        Returns:
            Tupla (cantidad_restante, slots_modificados).
        """
        remaining = quantity
        modified: list[tuple[int, int]] = []

        for slot_num, existing_slot in slots.items():
            if remaining <= 0:
                break

            # Solo apilar en slots del mismo item que no estén llenos
            if existing_slot.item_id == item_id and existing_slot.quantity < self.max_stack:
                new_slot, remaining = existing_slot.add_quantity(remaining, self.max_stack)

                # Actualizar en Redis
                await self.storage.set_slot(user_id, slot_num, new_slot)
                modified.append((slot_num, new_slot.quantity))

                logger.debug(
                    "Apilado en slot %d: %d -> %d",
                    slot_num,
                    existing_slot.quantity,
                    new_slot.quantity,
                )

        return remaining, modified

    async def _fill_empty_slots(
        self, user_id: int, item_id: int, quantity: int
    ) -> tuple[bool, list[tuple[int, int]]]:
        """Llena slots vacíos con el item.

        Args:
            user_id: ID del jugador.
            item_id: ID del item.
            quantity: Cantidad a agregar.

        Returns:
            Tupla (éxito, slots_modificados).
            éxito es False si no hay suficiente espacio.
        """
        remaining = quantity
        modified: list[tuple[int, int]] = []

        while remaining > 0:
            # Buscar un slot vacío
            empty_slot = await self.storage.find_empty_slot(user_id)

            if empty_slot is None:
                # No hay más espacio
                return False, []

            # Crear nuevo stack
            to_add = min(remaining, self.max_stack)
            new_slot = InventorySlot(item_id=item_id, quantity=to_add)

            await self.storage.set_slot(user_id, empty_slot, new_slot)
            modified.append((empty_slot, to_add))
            remaining -= to_add

            logger.debug(
                "Nuevo stack en slot %d: item_id=%d, quantity=%d",
                empty_slot,
                item_id,
                to_add,
            )

        return True, modified

    async def remove_item(self, user_id: int, slot: int, quantity: int) -> bool:
        """Remueve cantidad de un item de un slot.

        Args:
            user_id: ID del jugador.
            slot: Número de slot.
            quantity: Cantidad a remover.

        Returns:
            True si se removió correctamente.
        """
        if quantity <= 0:
            logger.warning("Cantidad inválida para remover: %d", quantity)
            return False

        current_slot = await self.storage.get_slot(user_id, slot)

        if current_slot is None:
            logger.warning("Slot %d está vacío para user_id %d", slot, user_id)
            return False

        if current_slot.quantity < quantity:
            logger.warning(
                "No hay suficiente cantidad en slot %d: tiene %d, se requiere %d",
                slot,
                current_slot.quantity,
                quantity,
            )
            return False

        # Remover cantidad
        new_slot = current_slot.remove_quantity(quantity)
        await self.storage.set_slot(user_id, slot, new_slot)

        logger.debug(
            "Removido de slot %d: %d -> %s",
            slot,
            current_slot.quantity,
            new_slot.quantity if new_slot else "vacío",
        )

        return True
