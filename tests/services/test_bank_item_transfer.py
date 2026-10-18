"""Concurrencia e incertidumbre de transferencias de objetos."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.repositories.inventory_repository import InventoryRepository
from src.services.bank_item_transfer import transfer_bank_item
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_competing_deposits_cannot_duplicate_source(redis_client):
    """Sólo un depósito puede consumir cuarenta objetos de los cuarenta y cinco del origen."""
    inventory = InventoryRepository(redis_client)
    await inventory.set_slot(1, 30, 1, 45)
    with patch("src.services.bank_item_transfer.require_durable", new=AsyncMock()):
        results = await asyncio.gather(
            *(
                transfer_bank_item(redis_client.redis, 1, 30, 40, "deposit", operation_id())
                for _ in range(2)
            )
        )
    assert sum(result["applied"] for result in results) == 1
    assert await inventory.get_slot(1, 30) == (1, 5)
    assert (await redis_client.hgetall(RedisKeys.bank(1)))["slot_1"] == "1:40"


@pytest.mark.asyncio
async def test_exec_ack_loss_and_identified_retry_do_not_repeat_items(redis_client):
    """El recibo y ambos inventarios sobreviven juntos al ACK perdido de EXEC."""
    inventory = InventoryRepository(redis_client)
    await inventory.set_slot(1, 30, 1, 45)
    pipeline_type = type(redis_client.redis.pipeline())
    original = pipeline_type.execute
    failed_once = False

    async def lose_ack(self, *args: object, **kwargs: object):
        nonlocal failed_once
        result = await original(self, *args, **kwargs)
        if not failed_once:
            failed_once = True
            message = "ACK perdido después de transferir objetos"
            raise RedisConnectionError(message)
        return result

    identity = operation_id()
    with (
        patch("src.services.bank_item_transfer.require_durable", new=AsyncMock()),
        patch.object(pipeline_type, "execute", lose_ack),
    ):
        result = await transfer_bank_item(redis_client.redis, 1, 30, 40, "deposit", identity)
        assert result["applied"]
        assert (
            await transfer_bank_item(redis_client.redis, 1, 30, 40, "deposit", identity) == result
        )
    assert await inventory.get_slot(1, 30) == (1, 5)
    assert (await redis_client.hgetall(RedisKeys.bank(1)))["slot_1"] == "1:40"
