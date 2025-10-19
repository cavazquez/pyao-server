"""Tests para InventorySlot (Value Object)."""

import pytest

from src.inventory_slot import InventorySlot


class TestInventorySlot:
    """Tests para InventorySlot."""

    def test_create_slot(self) -> None:
        """Test de creación de slot."""
        slot = InventorySlot(item_id=10, quantity=5)

        assert slot.item_id == 10
        assert slot.quantity == 5

    def test_parse_valid_string(self) -> None:
        """Test de parsing de string válido."""
        slot = InventorySlot.parse("10:5")

        assert slot is not None
        assert slot.item_id == 10
        assert slot.quantity == 5

    def test_parse_valid_bytes(self) -> None:
        """Test de parsing de bytes válidos."""
        slot = InventorySlot.parse(b"20:3")

        assert slot is not None
        assert slot.item_id == 20
        assert slot.quantity == 3

    def test_parse_empty_string(self) -> None:
        """Test de parsing de string vacío."""
        slot = InventorySlot.parse("")

        assert slot is None

    def test_parse_invalid_format(self) -> None:
        """Test de parsing de formato inválido."""
        slot = InventorySlot.parse("invalid")

        assert slot is None

    def test_parse_negative_values(self) -> None:
        """Test de parsing con valores negativos."""
        slot = InventorySlot.parse("-1:5")

        assert slot is None

    def test_to_string(self) -> None:
        """Test de conversión a string."""
        slot = InventorySlot(item_id=15, quantity=7)

        assert slot.to_string() == "15:7"

    def test_is_empty_false(self) -> None:
        """Test de slot no vacío."""
        slot = InventorySlot(item_id=10, quantity=5)

        assert slot.is_empty() is False

    def test_is_empty_true(self) -> None:
        """Test de slot vacío."""
        slot = InventorySlot(item_id=10, quantity=0)

        assert slot.is_empty() is True

    def test_can_stack_with_same_item(self) -> None:
        """Test de apilamiento con mismo item."""
        slot1 = InventorySlot(item_id=10, quantity=5)
        slot2 = InventorySlot(item_id=10, quantity=3)

        assert slot1.can_stack_with(slot2) is True

    def test_can_stack_with_different_item(self) -> None:
        """Test de apilamiento con item diferente."""
        slot1 = InventorySlot(item_id=10, quantity=5)
        slot2 = InventorySlot(item_id=20, quantity=3)

        assert slot1.can_stack_with(slot2) is False

    def test_add_quantity_within_limit(self) -> None:
        """Test de agregar cantidad dentro del límite."""
        slot = InventorySlot(item_id=10, quantity=5)

        new_slot, remaining = slot.add_quantity(3, max_stack=20)

        assert new_slot.quantity == 8
        assert remaining == 0

    def test_add_quantity_exceeds_limit(self) -> None:
        """Test de agregar cantidad que excede el límite."""
        slot = InventorySlot(item_id=10, quantity=18)

        new_slot, remaining = slot.add_quantity(5, max_stack=20)

        assert new_slot.quantity == 20
        assert remaining == 3

    def test_add_quantity_full_stack(self) -> None:
        """Test de agregar a stack lleno."""
        slot = InventorySlot(item_id=10, quantity=20)

        new_slot, remaining = slot.add_quantity(5, max_stack=20)

        assert new_slot.quantity == 20
        assert remaining == 5

    def test_remove_quantity_valid(self) -> None:
        """Test de remover cantidad válida."""
        slot = InventorySlot(item_id=10, quantity=5)

        new_slot = slot.remove_quantity(2)

        assert new_slot is not None
        assert new_slot.quantity == 3

    def test_remove_quantity_all(self) -> None:
        """Test de remover toda la cantidad."""
        slot = InventorySlot(item_id=10, quantity=5)

        new_slot = slot.remove_quantity(5)

        assert new_slot is None

    def test_remove_quantity_insufficient(self) -> None:
        """Test de remover más cantidad de la disponible."""
        slot = InventorySlot(item_id=10, quantity=3)

        new_slot = slot.remove_quantity(5)

        assert new_slot is None

    def test_immutability(self) -> None:
        """Test de inmutabilidad del Value Object."""
        slot = InventorySlot(item_id=10, quantity=5)

        # Intentar modificar debería fallar (frozen=True)
        with pytest.raises(AttributeError):
            slot.quantity = 10  # type: ignore[misc]
