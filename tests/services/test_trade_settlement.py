"""Journal, ACK perdido y barrera durable de la liquidación de comercio."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.trade_settlement import (
    OfferedItem,
    ParticipantOffer,
    get_trade_result,
    settle_trade,
)
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id


def offers():
    """Devuelve una oferta inmutable con recursos de ambos jugadores."""
    return (
        ParticipantOffer(1, 20, (OfferedItem(1, 101, 2),)),
        ParticipantOffer(2, 60, (OfferedItem(2, 202, 1),)),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_ack", [False, True])
async def test_competing_retries_and_lost_ack_apply_once(redis_client, lost_ack):
    """Inventarios y oro tienen una sola mutación pese a confirmaciones concurrentes."""
    player = PlayerRepository(redis_client)
    inventory = InventoryRepository(redis_client)
    await player.update_gold(1, 100)
    await player.update_gold(2, 200)
    await inventory.set_slot(1, 1, 101, 5)
    await inventory.set_slot(2, 2, 202, 3)
    original = type(redis_client.redis.pipeline()).execute
    failed_once = not lost_ack

    async def lose_ack(self, *args: object, **kwargs: object):
        nonlocal failed_once
        result = await original(self, *args, **kwargs)
        if not failed_once:
            failed_once = True
            message = "ACK perdido tras commit"
            raise RedisConnectionError(message)
        return result

    identity = operation_id()
    with (
        patch("src.services.trade_settlement.require_durable", new=AsyncMock()),
        patch.object(type(redis_client.redis.pipeline()), "execute", lose_ack),
    ):
        results = await asyncio.gather(
            *(settle_trade(redis_client.redis, identity, offers(), 30, 20) for _ in range(3))
        )
        assert all(result["applied"] for result in results)
        await redis_client.delete(f"operation:resources:{identity}")
        assert await settle_trade(redis_client.redis, identity, offers(), 30, 20) == results[0]
        assert await get_trade_result(redis_client.redis, identity, 1) == results[0]
        assert await get_trade_result(redis_client.redis, identity, 99) is None
        with pytest.raises(ValueError, match="otra oferta"):
            await settle_trade(
                redis_client.redis, identity, (ParticipantOffer(1, 21, ()), offers()[1]), 30, 20
            )
    assert await player.get_gold(1) == 140
    assert await player.get_gold(2) == 160
    assert await inventory.get_slot(1, 1) == (101, 3)
    assert await inventory.get_slot(2, 1) == (101, 2)


@pytest.mark.asyncio
async def test_durability_requires_same_dedicated_connection():
    """WAITAOF observa una escritura previa de su propia conexión, sin devolverla al pool."""
    redis = AsyncMock()
    dedicated = AsyncMock()
    dedicated.execute_command.return_value = [1, 0]
    redis.client = lambda: dedicated
    await require_durable(redis)
    dedicated.initialize.assert_awaited_once()
    dedicated.aclose.assert_awaited_once()
    dedicated.set.assert_awaited_once()
    dedicated.execute_command.assert_awaited_once_with("WAITAOF", 1, 0, 5000)
    redis.set.assert_not_awaited()
    dedicated.execute_command.return_value = [0, 0]
    with pytest.raises(RuntimeError, match="AOF"):
        await require_durable(redis)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["initialize", "set", "execute_command"])
async def test_cancelled_durability_returns_dedicated_connection(redis_client, monkeypatch, phase):
    """Una desconexión devuelve la conexión aun durante la entrada o la barrera AOF."""
    root = redis_client.redis
    dedicated = root.client()
    reached = asyncio.Event()
    original = getattr(dedicated, phase)

    async def interrupt(*args: object, **kwargs: object) -> None:
        if phase != "execute_command":
            await original(*args, **kwargs)
        reached.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(root, "client", lambda: dedicated)
    monkeypatch.setattr(dedicated, phase, interrupt)
    task = asyncio.create_task(require_durable(root))
    await asyncio.wait_for(reached.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert dedicated.connection is None
    assert not root.connection_pool._in_use_connections
    assert await root.ping()
