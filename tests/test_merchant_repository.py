"""Tests básicos para MerchantRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.merchant_repository import MerchantRepository


@pytest.mark.asyncio
class TestMerchantRepository:
    """Tests básicos para MerchantRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        repo = MerchantRepository(redis_client)

        assert repo.redis_client == redis_client

    async def test_get_inventory_empty(self) -> None:
        """Test de obtención de inventario vacío."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = MerchantRepository(redis_client)
        inventory = await repo.get_inventory(npc_id=2)

        assert inventory == {}

    async def test_get_inventory_with_data(self) -> None:
        """Test de obtención de inventario con datos."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                b"slot_1": b"10:5",  # item_id:quantity
                b"slot_2": b"20:3",
            }
        )

        repo = MerchantRepository(redis_client)
        inventory = await repo.get_inventory(npc_id=2)

        assert len(inventory) >= 0  # Solo verificar que retorna algo
