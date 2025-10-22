"""Tests de integración para InventoryRepository.

Estos tests verifican que InventoryRepository coordina correctamente
los componentes InventoryStorage y InventoryStackingStrategy.

Para tests unitarios de los componentes individuales, ver:
- test_inventory_slot.py
- test_inventory_storage.py
- test_inventory_stacking_strategy.py
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.inventory_repository import InventoryRepository


@pytest.mark.asyncio
class TestInventoryRepository:
    """Tests de integración para InventoryRepository."""

    async def test_init(self) -> None:
        """Test de inicialización con componentes."""
        redis_client = MagicMock()
        repo = InventoryRepository(redis_client, max_stack=20)

        assert repo.redis_client == redis_client
        assert repo.storage is not None
        assert repo.stacking is not None

    async def test_get_inventory_legacy_format(self) -> None:
        """Test que get_inventory retorna formato legacy para compatibilidad."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "slot_1": "10:5",
                "slot_2": "20:3",
            }
        )

        repo = InventoryRepository(redis_client)
        inventory = await repo.get_inventory(1)

        # Debe retornar formato legacy con todos los slots
        assert isinstance(inventory, dict)
        assert "slot_1" in inventory
        assert inventory["slot_1"] == "10:5"
        assert "slot_20" in inventory  # Debe incluir todos los slots

    async def test_add_item_integration(self) -> None:
        """Test de integración: agregar item usa storage y stacking."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})
        redis_client.redis.hget = AsyncMock(return_value=None)
        redis_client.redis.hset = AsyncMock()

        repo = InventoryRepository(redis_client)
        result = await repo.add_item(1, 10, 5)

        # Debe retornar slots modificados
        assert len(result) > 0
        # Debe haber llamado a Redis para guardar
        assert redis_client.redis.hset.called

    async def test_remove_item_integration(self) -> None:
        """Test de integración: remover item usa storage y stacking."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=b"10:5")
        redis_client.redis.hset = AsyncMock()

        repo = InventoryRepository(redis_client)
        result = await repo.remove_item(1, 1, 2)

        # Debe retornar True si fue exitoso
        assert result is True
        # Debe haber actualizado Redis
        assert redis_client.redis.hset.called

    async def test_get_slot_delegates_to_storage(self) -> None:
        """Test que get_slot delega correctamente a storage."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=b"10:5")

        repo = InventoryRepository(redis_client)
        slot_data = await repo.get_slot(1, 1)

        assert slot_data is not None
        assert slot_data == (10, 5)

    async def test_set_slot_delegates_to_storage(self) -> None:
        """Test que set_slot delega correctamente a storage."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = InventoryRepository(redis_client)
        result = await repo.set_slot(1, 1, 10, 5)

        assert result is True
        redis_client.redis.hset.assert_called_once()

    async def test_has_space_delegates_to_storage(self) -> None:
        """Test que has_space delega correctamente a storage."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={"slot_1": "10:5"})

        repo = InventoryRepository(redis_client)
        has_space = await repo.has_space(1)

        assert has_space is True
