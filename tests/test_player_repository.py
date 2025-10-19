"""Tests para PlayerRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.player_repository import PlayerRepository


@pytest.mark.asyncio
class TestPlayerRepository:
    """Tests para PlayerRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        repo = PlayerRepository(redis_client)

        assert repo.redis == redis_client

    async def test_get_gold(self) -> None:
        """Test de obtención de oro."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=b"1000")

        repo = PlayerRepository(redis_client)
        gold = await repo.get_gold(1)

        assert gold == 1000

    async def test_get_gold_not_found(self) -> None:
        """Test de obtención de oro cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=None)

        repo = PlayerRepository(redis_client)
        gold = await repo.get_gold(1)

        assert gold == 0

    async def test_update_gold(self) -> None:
        """Test de actualización de oro."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_gold(1, 500)

        redis_client.redis.hset.assert_called_once()

    async def test_update_hp(self) -> None:
        """Test de actualización de HP."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_hp(1, 50)

        redis_client.redis.hset.assert_called_once()

    async def test_update_experience(self) -> None:
        """Test de actualización de experiencia."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_experience(1, 1000)

        redis_client.redis.hset.assert_called_once()

    async def test_get_position(self) -> None:
        """Test de obtención de posición."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                b"x": b"50",
                b"y": b"50",
                b"map": b"1",
                b"heading": b"3",
            }
        )

        repo = PlayerRepository(redis_client)
        position = await repo.get_position(1)

        assert position is not None
        assert position["x"] == 50
        assert position["y"] == 50
        assert position["map"] == 1

    async def test_get_position_not_found(self) -> None:
        """Test de obtención de posición cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = PlayerRepository(redis_client)
        position = await repo.get_position(1)

        assert position is None

    async def test_set_position(self) -> None:
        """Test de configuración de posición."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_position(1, 50, 50, 1, 3)

        redis_client.redis.hset.assert_called_once()
