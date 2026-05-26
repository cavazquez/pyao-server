"""Tests para ServerRepository."""

from unittest.mock import AsyncMock

import pytest

from src.repositories.server_repository import ServerRepository
from src.utils.redis_config import RedisKeys
from tests.conftest import create_mock_redis_client


@pytest.mark.asyncio
class TestServerRepository:
    """Tests para ServerRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = create_mock_redis_client()
        repo = ServerRepository(redis_client)

        assert repo.redis_client == redis_client

    async def test_get_motd(self) -> None:
        """Test de obtención de MOTD."""
        redis_client = create_mock_redis_client()
        redis_client.get = AsyncMock(return_value=b"Bienvenido!")

        repo = ServerRepository(redis_client)
        motd = await repo.get_motd()

        assert "Bienvenido" in motd

    async def test_set_motd(self) -> None:
        """Test de configuración de MOTD."""
        redis_client = create_mock_redis_client()
        redis_client.set = AsyncMock()

        repo = ServerRepository(redis_client)
        await repo.set_motd("Nuevo mensaje")

        redis_client.set.assert_called_once()

    async def test_get_uptime_start(self) -> None:
        """Test de obtención de uptime start."""
        redis_client = create_mock_redis_client()
        redis_client.get = AsyncMock(return_value=b"1234567890")

        repo = ServerRepository(redis_client)
        uptime = await repo.get_uptime_start()

        assert uptime == 1234567890

    async def test_set_uptime_start(self) -> None:
        """Test de configuración de uptime start."""
        redis_client = create_mock_redis_client()
        redis_client.set = AsyncMock()

        repo = ServerRepository(redis_client)
        await repo.set_uptime_start(1234567890)

        redis_client.set.assert_called_once()

    async def test_get_dice_min_value(self) -> None:
        """Test de obtención de valor mínimo de dados."""
        redis_client = create_mock_redis_client()
        redis_client.get = AsyncMock(return_value=b"6")

        repo = ServerRepository(redis_client)
        value = await repo.get_dice_min_value()

        assert value == 6

    async def test_get_dice_max_value(self) -> None:
        """Test de obtención de valor máximo de dados."""
        redis_client = create_mock_redis_client()
        redis_client.get = AsyncMock(return_value=b"18")

        repo = ServerRepository(redis_client)
        value = await repo.get_dice_max_value()

        assert value == 18

    async def test_reset_connections_count(self) -> None:
        """Test de reseteo del contador de conexiones."""
        redis_client = create_mock_redis_client()
        redis_client.set = AsyncMock()

        repo = ServerRepository(redis_client)
        await repo.reset_connections_count()

        redis_client.set.assert_called_once_with(RedisKeys.SERVER_CONNECTIONS_COUNT, "0")
