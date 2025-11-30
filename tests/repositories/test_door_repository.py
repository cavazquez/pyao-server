"""Tests para DoorRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.door_repository import DoorRepository


@pytest.fixture
def mock_redis_client() -> MagicMock:
    """Mock de RedisClient."""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.delete = AsyncMock()

    client = MagicMock()
    client.redis = redis_mock
    return client


@pytest.mark.asyncio
async def test_get_door_state_exists(mock_redis_client: MagicMock) -> None:
    """Test obtener estado de puerta que existe."""
    mock_redis_client.redis.get = AsyncMock(return_value=b"123:1")

    repo = DoorRepository(redis=mock_redis_client)
    result = await repo.get_door_state(1, 10, 20)

    assert result == (123, True)
    mock_redis_client.redis.get.assert_called_once_with("door:1:10:20")


@pytest.mark.asyncio
async def test_get_door_state_not_exists(mock_redis_client: MagicMock) -> None:
    """Test obtener estado de puerta que no existe."""
    mock_redis_client.redis.get = AsyncMock(return_value=None)

    repo = DoorRepository(redis=mock_redis_client)
    result = await repo.get_door_state(1, 10, 20)

    assert result is None


@pytest.mark.asyncio
async def test_get_door_state_closed(mock_redis_client: MagicMock) -> None:
    """Test obtener estado de puerta cerrada."""
    mock_redis_client.redis.get = AsyncMock(return_value="456:0")

    repo = DoorRepository(redis=mock_redis_client)
    result = await repo.get_door_state(1, 10, 20)

    assert result == (456, False)


@pytest.mark.asyncio
async def test_get_door_state_no_redis() -> None:
    """Test cuando no hay Redis disponible."""
    repo = DoorRepository(redis=None)
    result = await repo.get_door_state(1, 10, 20)

    assert result is None


@pytest.mark.asyncio
async def test_set_door_state_open(mock_redis_client: MagicMock) -> None:
    """Test guardar estado de puerta abierta."""
    repo = DoorRepository(redis=mock_redis_client)
    result = await repo.set_door_state(1, 10, 20, 123, True)  # noqa: FBT003

    assert result is True
    mock_redis_client.redis.set.assert_called_once_with("door:1:10:20", "123:1")


@pytest.mark.asyncio
async def test_set_door_state_closed(mock_redis_client: MagicMock) -> None:
    """Test guardar estado de puerta cerrada."""
    repo = DoorRepository(redis=mock_redis_client)
    result = await repo.set_door_state(1, 10, 20, 123, False)  # noqa: FBT003

    assert result is True
    mock_redis_client.redis.set.assert_called_once_with("door:1:10:20", "123:0")


@pytest.mark.asyncio
async def test_set_door_state_no_redis() -> None:
    """Test cuando no hay Redis disponible."""
    repo = DoorRepository(redis=None)
    result = await repo.set_door_state(1, 10, 20, 123, True)  # noqa: FBT003

    assert result is False


@pytest.mark.asyncio
async def test_delete_door_state(mock_redis_client: MagicMock) -> None:
    """Test eliminar estado de puerta."""
    repo = DoorRepository(redis=mock_redis_client)
    result = await repo.delete_door_state(1, 10, 20)

    assert result is True
    mock_redis_client.redis.delete.assert_called_once_with("door:1:10:20")


@pytest.mark.asyncio
async def test_delete_door_state_no_redis() -> None:
    """Test cuando no hay Redis disponible."""
    repo = DoorRepository(redis=None)
    result = await repo.delete_door_state(1, 10, 20)

    assert result is False
