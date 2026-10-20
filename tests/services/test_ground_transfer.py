"""Transferencia de suelo con fallas de EXEC, posición cambiada y replay de resultados."""

from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GroundState
from src.utils.ground_storage import encode_fields, read_ground
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["pickup", "drop_item", "drop_gold"])
@pytest.mark.parametrize("after_exec", [False, True])
async def test_fault_at_exec_and_identified_retry_keep_resources_together(
    redis_client, action, after_exec
):
    """La caída antes o después de EXEC no separa suelo, objetos y monedas."""
    player, inventory = PlayerRepository(redis_client), InventoryRepository(redis_client)
    await player.set_position(1, 50, 50, 1)
    await player.update_gold(1, 100)
    await inventory.set_slot(1, 30, 1, 5)
    raw = '{"50,50":[{"item_id":1,"quantity":2}]}'
    await redis_client.redis.hset(
        RedisKeys.ground_items(1), mapping=encode_fields(GroundState(1, raw))
    )
    stack_id = GroundState(1, raw).tile(50, 50)[0]["stack_id"]
    request = GroundRequest(
        1, 1, 50, 50, action, slot=30, quantity=2, expected_stack=stack_id, expected_item_id=1
    )
    pipeline_type = type(redis_client.redis.pipeline())
    original = pipeline_type.execute
    failed_once = False

    async def faulty_exec(self, *args: object, **kwargs: object):
        nonlocal failed_once
        if failed_once:
            return await original(self, *args, **kwargs)
        failed_once = True
        if after_exec:
            await original(self, *args, **kwargs)
        message = "Caída simulada alrededor de EXEC de suelo"
        raise RedisConnectionError(message)

    identity = operation_id()
    with (
        patch("src.services.ground_transfer.require_durable", new=AsyncMock()),
        patch.object(pipeline_type, "execute", faulty_exec),
    ):
        result = await transfer_ground(redis_client.redis, request, identity)
        assert result["applied"]
        assert await transfer_ground(redis_client.redis, request, identity) == result
    assert await inventory.get_slot(1, 30) == (
        1,
        7 if action == "pickup" else 3 if action == "drop_item" else 5,
    )
    assert await player.get_gold(1) == (98 if action == "drop_gold" else 100)
    rows = (await read_ground(redis_client.redis, 1)).tile(50, 50)
    assert sum(item["quantity"] for item in rows) == (0 if action == "pickup" else 4)


@pytest.mark.asyncio
async def test_position_change_rejects_without_debit(redis_client):
    """Una teletransportación concurrente no deja un objeto pagado en la posición anterior."""
    player = PlayerRepository(redis_client)
    await player.update_gold(1, 100)
    await player.set_position(1, 51, 50, 1)
    request = GroundRequest(1, 1, 50, 50, "drop_gold", quantity=40)
    with patch("src.services.ground_transfer.require_durable", new=AsyncMock()):
        result = await transfer_ground(redis_client.redis, request, operation_id())
    assert not result["applied"]
    assert await player.get_gold(1) == 100
    assert await redis_client.get(RedisKeys.ground_items(1)) is None
