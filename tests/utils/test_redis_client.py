"""Tests para el cliente Redis."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fakeredis import aioredis

import redis
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisConfig, RedisKeys


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[RedisClient]:
    """Fixture que proporciona un cliente Redis con fakeredis.

    Yields:
        Cliente Redis configurado con fakeredis.
    """
    client = RedisClient()
    # Resetear el singleton para cada test
    RedisClient._instance = None
    RedisClient._redis = None

    client = RedisClient()
    # Usar fakeredis en lugar de Redis real
    client._redis = await aioredis.FakeRedis(decode_responses=True)

    yield client

    await client.disconnect()
    # Limpiar singleton
    RedisClient._instance = None
    RedisClient._redis = None


class TestRedisClient:
    """Tests para RedisClient."""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self) -> None:
        """Verifica que RedisClient implementa el patrón singleton."""
        client1 = RedisClient()
        client2 = RedisClient()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_server_host_default(self, redis_client: RedisClient) -> None:
        """Verifica que get_server_host retorna el valor por defecto."""
        host = await redis_client.get_server_host()
        assert host == "0.0.0.0"

    @pytest.mark.asyncio
    async def test_get_server_port_default(self, redis_client: RedisClient) -> None:
        """Verifica que get_server_port retorna el valor por defecto."""
        port = await redis_client.get_server_port()
        assert port == 7666

    @pytest.mark.asyncio
    async def test_set_server_host(self, redis_client: RedisClient) -> None:
        """Verifica que se puede establecer el host del servidor."""
        await redis_client.set_server_host("127.0.0.1")
        host = await redis_client.get_server_host()
        assert host == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_set_server_port(self, redis_client: RedisClient) -> None:
        """Verifica que se puede establecer el puerto del servidor."""
        await redis_client.set_server_port(8080)
        port = await redis_client.get_server_port()
        assert port == 8080

    @pytest.mark.asyncio
    async def test_increment_connections(self, redis_client: RedisClient) -> None:
        """Verifica que se puede incrementar el contador de conexiones."""
        count1 = await redis_client.increment_connections()
        count2 = await redis_client.increment_connections()
        assert count1 == 1
        assert count2 == 2

    @pytest.mark.asyncio
    async def test_decrement_connections(self, redis_client: RedisClient) -> None:
        """Verifica que se puede decrementar el contador de conexiones."""
        await redis_client.increment_connections()
        await redis_client.increment_connections()
        count = await redis_client.decrement_connections()
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_connections_count(self, redis_client: RedisClient) -> None:
        """Verifica que se puede obtener el contador de conexiones."""
        await redis_client.increment_connections()
        await redis_client.increment_connections()
        count = await redis_client.get_connections_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_set_player_session(self, redis_client: RedisClient) -> None:
        """Verifica que se puede establecer una sesión de jugador."""
        user_id = 123
        data = {"username": "test_user", "level": "10"}
        await redis_client.set_player_session(user_id, data)

        session = await redis_client.get_player_session(user_id)
        assert session["username"] == "test_user"
        assert session["level"] == "10"

    @pytest.mark.asyncio
    async def test_delete_player_session(self, redis_client: RedisClient) -> None:
        """Verifica que se puede eliminar una sesión de jugador."""
        user_id = 123
        data = {"username": "test_user"}
        await redis_client.set_player_session(user_id, data)
        await redis_client.delete_player_session(user_id)

        session = await redis_client.get_player_session(user_id)
        assert session == {}

    @pytest.mark.asyncio
    async def test_update_player_last_seen(self, redis_client: RedisClient) -> None:
        """Verifica que se puede actualizar el último acceso de un jugador."""
        user_id = 123
        await redis_client.update_player_last_seen(user_id)

        key = RedisKeys.session_last_seen(user_id)
        value = await redis_client.redis.get(key)
        assert value is not None
        assert int(value) > 0

    @pytest.mark.asyncio
    async def test_connection_error_handling(self) -> None:
        """Verifica que ConnectionError se captura correctamente."""
        # Resetear singleton
        RedisClient._instance = None
        RedisClient._redis = None

        client = RedisClient()
        config = RedisConfig(host="invalid-host", port=9999)

        # Mock Redis para simular ConnectionError en ping()
        mock_instance = MagicMock()
        mock_instance.ping = AsyncMock(
            side_effect=redis.ConnectionError("Error 111 connecting to invalid-host:9999")
        )

        with patch("redis.asyncio.Redis", return_value=mock_instance):
            with pytest.raises(redis.ConnectionError):
                await client.connect(config)

            # Verificar que _redis se limpió
            assert client._redis is None

        # Limpiar singleton
        RedisClient._instance = None
        RedisClient._redis = None


class TestRedisConfig:
    """Tests para RedisConfig."""

    def test_redis_config_defaults(self) -> None:
        """Verifica los valores por defecto de RedisConfig."""
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.decode_responses is True

    def test_redis_config_custom(self) -> None:
        """Verifica que se pueden establecer valores personalizados."""
        config = RedisConfig(host="redis.example.com", port=6380, db=1)
        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1


class TestRedisKeys:
    """Tests para RedisKeys."""

    def test_session_active_key(self) -> None:
        """Verifica la generación de claves de sesión activa."""
        key = RedisKeys.session_active(123)
        assert key == "session:123:active"

    def test_session_last_seen_key(self) -> None:
        """Verifica la generación de claves de último acceso."""
        key = RedisKeys.session_last_seen(456)
        assert key == "session:456:last_seen"

    def test_player_position_key(self) -> None:
        """Verifica la generación de claves de posición."""
        key = RedisKeys.player_position(789)
        assert key == "player:789:position"

    def test_player_stats_key(self) -> None:
        """Verifica la generación de claves de estadísticas."""
        key = RedisKeys.player_stats(101)
        assert key == "player:101:stats"

    def test_player_inventory_key(self) -> None:
        """Verifica la generación de claves de inventario."""
        key = RedisKeys.player_inventory(202)
        assert key == "player:202:inventory"
