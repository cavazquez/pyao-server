"""Tests para MerchantDataLoader."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.merchant_data_loader import MerchantDataLoader
from src.repositories.merchant_repository import MerchantRepository
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys
from tests.conftest import create_mock_redis_client


@pytest.fixture
def redis_client() -> RedisClient:
    """Fixture para crear un cliente Redis mockeado."""
    return create_mock_redis_client()


@pytest.fixture
def mock_merchant_repo() -> AsyncMock:
    """Repositorio de mercaderes mockeado."""
    repo = AsyncMock(spec=MerchantRepository)
    repo.load_inventory_slots = AsyncMock(return_value=1)
    return repo


@pytest.mark.asyncio
async def test_merchant_loader_get_name(redis_client: RedisClient) -> None:
    """Verifica que get_name() retorna el nombre correcto."""
    loader = MerchantDataLoader(redis_client)
    assert loader.get_name() == "Merchant Inventories"


@pytest.mark.asyncio
async def test_merchant_loader_initialization(redis_client: RedisClient) -> None:
    """Verifica que el loader se inicializa correctamente."""
    loader = MerchantDataLoader(redis_client)
    assert loader.redis_client is redis_client
    assert isinstance(loader._merchant_repo, MerchantRepository)
    assert loader.TOML_FILE == "data/npcs/merchants.toml"


@pytest.mark.asyncio
async def test_merchant_loader_load_delegates_to_repository(
    redis_client: RedisClient,
    mock_merchant_repo: AsyncMock,
) -> None:
    """Verifica que load() delega en MerchantRepository."""
    loader = MerchantDataLoader(redis_client)
    loader._merchant_repo = mock_merchant_repo
    mock_merchant_repo.load_inventory_slots = AsyncMock(return_value=2)

    await loader.load()

    assert mock_merchant_repo.clear_merchant.await_count > 0
    assert mock_merchant_repo.load_inventory_slots.await_count > 0
    assert mock_merchant_repo.set_item_id_index.await_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_load_integration(redis_client: RedisClient) -> None:
    """Integración loader → repo → Redis mock."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    assert redis_client.hset.await_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_load_creates_correct_keys(redis_client: RedisClient) -> None:
    """Verifica que load() crea las keys correctas en Redis."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    expected_key = RedisKeys.merchant_inventory(7)
    calls = redis_client.hset.await_args_list
    keys_used = {call.args[0] for call in calls}
    assert expected_key in keys_used


@pytest.mark.asyncio
async def test_merchant_loader_load_correct_format(redis_client: RedisClient) -> None:
    """Verifica que load() usa el formato correcto item_id:quantity."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    calls = redis_client.hset.await_args_list
    for call in calls:
        value = call.args[2]
        assert ":" in value
        parts = value.split(":")
        assert len(parts) == 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()


@pytest.mark.asyncio
async def test_merchant_loader_clear_delegates_to_repository(
    redis_client: RedisClient,
    mock_merchant_repo: AsyncMock,
) -> None:
    """Verifica que clear() delega en MerchantRepository."""
    loader = MerchantDataLoader(redis_client)
    loader._merchant_repo = mock_merchant_repo

    await loader.clear()

    assert mock_merchant_repo.clear_merchant.await_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_clear_integration(redis_client: RedisClient) -> None:
    """Integración clear() → repo → Redis mock."""
    loader = MerchantDataLoader(redis_client)

    await loader.clear()

    assert redis_client.delete.await_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_clear_deletes_correct_keys(redis_client: RedisClient) -> None:
    """Verifica que clear() elimina las keys correctas."""
    loader = MerchantDataLoader(redis_client)

    await loader.clear()

    expected_key = RedisKeys.merchant_inventory(7)
    calls = redis_client.delete.await_args_list
    keys_deleted = {call.args[0] for call in calls}
    assert expected_key in keys_deleted


@pytest.mark.asyncio
async def test_merchant_loader_initialize_without_force_clear(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize() sin force_clear solo carga datos."""
    loader = MerchantDataLoader(redis_client)

    await loader.initialize(force_clear=False)

    assert redis_client.hset.await_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_initialize_with_force_clear(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize() con force_clear limpia y luego carga."""
    loader = MerchantDataLoader(redis_client)

    await loader.initialize(force_clear=True)

    assert redis_client.delete.await_count > 0
    assert redis_client.hset.await_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_handles_missing_file() -> None:
    """Verifica que load() maneja correctamente un archivo faltante."""
    redis_client = MagicMock(spec=RedisClient)
    redis_client.redis = MagicMock()

    loader = MerchantDataLoader(redis_client)
    loader._merchant_repo = AsyncMock(spec=MerchantRepository)
    loader.TOML_FILE = "data/nonexistent_file.toml"

    await loader.load()

    loader._merchant_repo.clear_merchant.assert_not_called()


@pytest.mark.asyncio
async def test_merchant_loader_loads_multiple_merchants(redis_client: RedisClient) -> None:
    """Verifica que load() puede cargar múltiples mercaderes si existen."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    assert redis_client.hset.await_count >= 10
