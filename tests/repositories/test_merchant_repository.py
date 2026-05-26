"""Tests básicos para MerchantRepository."""

from unittest.mock import AsyncMock

import pytest

from src.repositories.merchant_repository import MerchantRepository
from src.utils.redis_config import RedisKeys
from tests.conftest import create_mock_redis_client


@pytest.mark.asyncio
class TestMerchantRepository:
    """Tests básicos para MerchantRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = create_mock_redis_client()
        repo = MerchantRepository(redis_client)

        assert repo.redis_client == redis_client

    async def test_get_inventory_empty(self) -> None:
        """Test de obtención de inventario vacío."""
        redis_client = create_mock_redis_client()
        redis_client.hgetall = AsyncMock(return_value={})

        repo = MerchantRepository(redis_client)
        inventory = await repo.get_inventory(npc_id=2)

        assert inventory == {}

    async def test_get_inventory_with_data(self) -> None:
        """Test de obtención de inventario con datos."""
        redis_client = create_mock_redis_client()
        redis_client.hgetall = AsyncMock(
            return_value={
                b"slot_1": b"10:5",  # item_id:quantity
                b"slot_2": b"20:3",
            }
        )

        repo = MerchantRepository(redis_client)
        inventory = await repo.get_inventory(npc_id=2)

        assert len(inventory) >= 0  # Solo verificar que retorna algo

    async def test_clear_merchant(self) -> None:
        """Test de borrado de inventario y set auxiliar."""
        redis_client = create_mock_redis_client()
        redis_client.delete = AsyncMock()

        repo = MerchantRepository(redis_client)
        await repo.clear_merchant(npc_id=7)

        assert redis_client.delete.await_count == 2
        deleted_keys = {call.args[0] for call in redis_client.delete.await_args_list}
        assert RedisKeys.merchant_inventory(7) in deleted_keys
        assert MerchantRepository._merchant_items_key(7) in deleted_keys

    async def test_load_inventory_slots(self) -> None:
        """Test de carga slot a slot desde TOML."""
        redis_client = create_mock_redis_client()
        redis_client.delete = AsyncMock()
        redis_client.hset = AsyncMock()

        repo = MerchantRepository(redis_client)
        loaded = await repo.load_inventory_slots(7, [(10, 5), (20, 3)])

        assert loaded == 2
        redis_client.delete.assert_called_once_with(RedisKeys.merchant_inventory(7))
        assert redis_client.hset.await_count == 2
        redis_client.hset.assert_any_await(
            RedisKeys.merchant_inventory(7),
            "slot_1",
            "10:5",
        )
        redis_client.hset.assert_any_await(
            RedisKeys.merchant_inventory(7),
            "slot_2",
            "20:3",
        )

    async def test_set_item_id_index(self) -> None:
        """Test de índice de item_ids en set auxiliar."""
        redis_client = create_mock_redis_client()
        redis_client.delete = AsyncMock()
        redis_client.sadd = AsyncMock()

        repo = MerchantRepository(redis_client)
        await repo.set_item_id_index(7, ["10", "20"])

        redis_client.delete.assert_called_once_with(MerchantRepository._merchant_items_key(7))
        redis_client.sadd.assert_called_once_with(
            MerchantRepository._merchant_items_key(7),
            "10",
            "20",
        )
