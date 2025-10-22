"""Tests para InventoryStackingStrategy."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.inventory_slot import InventorySlot
from src.utils.inventory_stacking_strategy import InventoryStackingStrategy


@pytest.mark.asyncio
class TestInventoryStackingStrategy:
    """Tests para InventoryStackingStrategy."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        storage = MagicMock()
        strategy = InventoryStackingStrategy(storage, max_stack=20)

        assert strategy.storage == storage
        assert strategy.max_stack == 20

    async def test_add_item_to_empty_inventory(self) -> None:
        """Test de agregar item a inventario vacío."""
        storage = MagicMock()
        storage.get_all_slots = AsyncMock(return_value={})
        storage.find_empty_slot = AsyncMock(return_value=1)
        storage.set_slot = AsyncMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.add_item(1, 10, 5)

        assert len(result) == 1
        assert result[0] == (1, 5)
        storage.set_slot.assert_called_once()

    async def test_add_item_stacking_existing(self) -> None:
        """Test de agregar item apilando en slot existente."""
        storage = MagicMock()
        existing_slot = InventorySlot(item_id=10, quantity=5)
        storage.get_all_slots = AsyncMock(return_value={1: existing_slot})
        storage.set_slot = AsyncMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.add_item(1, 10, 3)

        assert len(result) == 1
        assert result[0] == (1, 8)

    async def test_add_item_exceeds_stack_limit(self) -> None:
        """Test de agregar item que excede límite de stack."""
        storage = MagicMock()
        existing_slot = InventorySlot(item_id=10, quantity=18)
        storage.get_all_slots = AsyncMock(return_value={1: existing_slot})
        storage.find_empty_slot = AsyncMock(return_value=2)
        storage.set_slot = AsyncMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.add_item(1, 10, 5)

        # Debería llenar slot 1 (18+2=20) y crear slot 2 (3)
        assert len(result) == 2
        assert (1, 20) in result
        assert (2, 3) in result

    async def test_add_item_no_space(self) -> None:
        """Test de agregar item sin espacio disponible."""
        storage = MagicMock()
        storage.get_all_slots = AsyncMock(return_value={})
        storage.find_empty_slot = AsyncMock(return_value=None)

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.add_item(1, 10, 5)

        assert result == []

    async def test_add_item_multiple_stacks(self) -> None:
        """Test de agregar item que requiere múltiples stacks."""
        storage = MagicMock()
        storage.get_all_slots = AsyncMock(return_value={})
        storage.find_empty_slot = AsyncMock(side_effect=[1, 2, 3])
        storage.set_slot = AsyncMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.add_item(1, 10, 45)

        # Debería crear 3 stacks: 20+20+5
        assert len(result) == 3
        assert (1, 20) in result
        assert (2, 20) in result
        assert (3, 5) in result

    async def test_remove_item_valid(self) -> None:
        """Test de remover item válido."""
        storage = MagicMock()
        existing_slot = InventorySlot(item_id=10, quantity=5)
        storage.get_slot = AsyncMock(return_value=existing_slot)
        storage.set_slot = AsyncMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.remove_item(1, 1, 2)

        assert result is True
        storage.set_slot.assert_called_once()

    async def test_remove_item_all_quantity(self) -> None:
        """Test de remover toda la cantidad."""
        storage = MagicMock()
        existing_slot = InventorySlot(item_id=10, quantity=5)
        storage.get_slot = AsyncMock(return_value=existing_slot)
        storage.set_slot = AsyncMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.remove_item(1, 1, 5)

        assert result is True
        # Debería llamar con None para vaciar el slot
        storage.set_slot.assert_called_once()

    async def test_remove_item_insufficient_quantity(self) -> None:
        """Test de remover más cantidad de la disponible."""
        storage = MagicMock()
        existing_slot = InventorySlot(item_id=10, quantity=3)
        storage.get_slot = AsyncMock(return_value=existing_slot)

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.remove_item(1, 1, 5)

        assert result is False

    async def test_remove_item_empty_slot(self) -> None:
        """Test de remover de slot vacío."""
        storage = MagicMock()
        storage.get_slot = AsyncMock(return_value=None)

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.remove_item(1, 1, 1)

        assert result is False

    async def test_remove_item_invalid_quantity(self) -> None:
        """Test de remover cantidad inválida."""
        storage = MagicMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.remove_item(1, 1, 0)

        assert result is False

    async def test_add_item_invalid_quantity(self) -> None:
        """Test de agregar cantidad inválida."""
        storage = MagicMock()

        strategy = InventoryStackingStrategy(storage, max_stack=20)
        result = await strategy.add_item(1, 10, 0)

        assert result == []
