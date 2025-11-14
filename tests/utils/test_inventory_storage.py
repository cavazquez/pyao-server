"""Tests para InventoryStorage."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.inventory_slot import InventorySlot
from src.utils.inventory_storage import InventoryStorage


@pytest.mark.asyncio
class TestInventoryStorage:
    """Tests para InventoryStorage."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        storage = InventoryStorage(redis_client)

        assert storage.redis_client == redis_client
        assert storage.MAX_SLOTS == 30

    async def test_get_slot_valid(self) -> None:
        """Test de obtención de slot válido."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=b"10:5")

        storage = InventoryStorage(redis_client)
        slot = await storage.get_slot(1, 1)

        assert slot is not None
        assert slot.item_id == 10
        assert slot.quantity == 5

    async def test_get_slot_empty(self) -> None:
        """Test de obtención de slot vacío."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=None)

        storage = InventoryStorage(redis_client)
        slot = await storage.get_slot(1, 1)

        assert slot is None

    async def test_get_slot_invalid_number(self) -> None:
        """Test de obtención de slot con número inválido."""
        # Create an AsyncMock for the Redis client
        redis_client = MagicMock()
        redis_client.redis = AsyncMock()

        storage = InventoryStorage(redis_client)
        # Test with a slot number that's greater than max_inventory_slots (30)
        slot = await storage.get_slot(1, 31)  # Fuera de rango (31 > 30)

        assert slot is None
        # Verify Redis was never called since the slot is invalid
        redis_client.redis.hget.assert_not_awaited()

    async def test_set_slot_with_item(self) -> None:
        """Test de configurar slot con item."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        storage = InventoryStorage(redis_client)
        inventory_slot = InventorySlot(item_id=10, quantity=5)
        result = await storage.set_slot(1, 1, inventory_slot)

        assert result is True
        redis_client.redis.hset.assert_called_once()

    async def test_set_slot_empty(self) -> None:
        """Test de vaciar slot."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        storage = InventoryStorage(redis_client)
        result = await storage.set_slot(1, 1, None)

        assert result is True
        redis_client.redis.hset.assert_called_once()

    async def test_clear_slot(self) -> None:
        """Test de limpiar slot."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        storage = InventoryStorage(redis_client)
        result = await storage.clear_slot(1, 1)

        assert result is True

    async def test_get_all_slots_empty(self) -> None:
        """Test de obtener todos los slots cuando está vacío."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})
        redis_client.redis.hset = AsyncMock()

        storage = InventoryStorage(redis_client)
        slots = await storage.get_all_slots(1)

        assert slots == {}

    async def test_get_all_slots_with_items(self) -> None:
        """Test de obtener todos los slots con items."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "slot_1": "10:5",
                "slot_2": "20:3",
                "slot_3": "",
            }
        )

        storage = InventoryStorage(redis_client)
        slots = await storage.get_all_slots(1)

        assert len(slots) == 2
        assert 1 in slots
        assert 2 in slots
        assert 3 not in slots  # Vacío no se incluye

    async def test_find_empty_slot(self) -> None:
        """Test de encontrar slot vacío."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "slot_1": "10:5",
                "slot_2": "20:3",
            }
        )

        storage = InventoryStorage(redis_client)
        empty_slot = await storage.find_empty_slot(1)

        assert empty_slot == 3

    async def test_find_empty_slot_full(self) -> None:
        """Test de buscar slot vacío cuando está lleno."""
        redis_client = MagicMock()
        # Simular inventario lleno
        full_inventory = {f"slot_{i}".encode(): b"10:5" for i in range(1, 21)}
        full_inventory = {f"slot_{i}": "10:5" for i in range(1, 31)}
        redis_client.redis.hgetall = AsyncMock(return_value=full_inventory)

        storage = InventoryStorage(redis_client)
        empty_slot = await storage.find_empty_slot(1)

        assert empty_slot is None

    async def test_has_space_true(self) -> None:
        """Test de verificar espacio disponible."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={"slot_1": "10:5"})

        storage = InventoryStorage(redis_client)
        has_space = await storage.has_space(1)

        assert has_space is True

    async def test_has_space_false(self) -> None:
        """Test de verificar sin espacio disponible."""
        redis_client = MagicMock()
        # Simular inventario lleno
        full_inventory = {f"slot_{i}": "10:5" for i in range(1, 31)}
        redis_client.redis.hgetall = AsyncMock(return_value=full_inventory)

        storage = InventoryStorage(redis_client)
        has_space = await storage.has_space(1)

        assert has_space is False
