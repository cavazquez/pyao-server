"""Tests para MerchantDataLoader."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.merchant_data_loader import MerchantDataLoader
from src.repositories.merchant_repository import MerchantRepository
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys


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
async def test_merchant_loader_load_preserves_existing_stock(
    redis_client: RedisClient,
    mock_merchant_repo: AsyncMock,
) -> None:
    """Una carga normal adopta el inventario Redis sin limpiarlo ni resembrarlo."""
    loader = MerchantDataLoader(redis_client)
    loader._merchant_repo = mock_merchant_repo
    mock_merchant_repo.load_inventory_slots = AsyncMock(return_value=2)
    stock = {"slot_1": "15:1", "slot_2": "139:3"}
    await redis_client.redis.hset(RedisKeys.merchant_inventory(7), mapping=stock)

    await loader.load()

    mock_merchant_repo.clear_merchant.assert_not_awaited()
    mock_merchant_repo.load_inventory_slots.assert_not_awaited()
    assert await redis_client.redis.hgetall(RedisKeys.merchant_inventory(7)) == stock


@pytest.mark.asyncio
async def test_merchant_loader_load_integration(redis_client: RedisClient) -> None:
    """Integración loader → repo → Redis mock."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    assert await redis_client.redis.exists(RedisKeys.merchant_inventory(7))


@pytest.mark.asyncio
async def test_merchant_loader_load_creates_correct_keys(redis_client: RedisClient) -> None:
    """Verifica que load() crea las keys correctas en Redis."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    expected_key = RedisKeys.merchant_inventory(7)
    assert await redis_client.redis.exists(expected_key)


@pytest.mark.asyncio
async def test_merchant_loader_load_correct_format(redis_client: RedisClient) -> None:
    """Verifica que load() usa el formato correcto item_id:quantity."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    inventory = await redis_client.redis.hgetall(RedisKeys.merchant_inventory(7))
    assert inventory
    for field, value in inventory.items():
        if not field.startswith("slot_") or not value:
            continue
        item_id, quantity = value.split(":")
        assert item_id.isdigit()
        assert quantity.isdigit()


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
    """La limpieza administrativa retira datos existentes y su política."""
    loader = MerchantDataLoader(redis_client)
    await loader.load()
    assert await redis_client.redis.exists("merchant:7:catalog")

    await loader.clear()
    assert not await redis_client.redis.exists("merchant:7:catalog")

    assert not await redis_client.redis.exists(RedisKeys.merchant_inventory(7))


@pytest.mark.asyncio
async def test_merchant_loader_clear_deletes_correct_keys(redis_client: RedisClient) -> None:
    """La limpieza explícita elimina los slots y su índice auxiliar."""
    loader = MerchantDataLoader(redis_client)
    await loader.load()
    assert await redis_client.redis.scard("merchant:7:items") > 0

    await loader.clear()
    assert not await redis_client.redis.exists("merchant:7:items")

    expected_key = RedisKeys.merchant_inventory(7)
    assert not await redis_client.redis.exists(expected_key)


@pytest.mark.asyncio
async def test_merchant_loader_initialize_without_force_clear(
    redis_client: RedisClient,
) -> None:
    """La inicialización normal conserva las cantidades confirmadas."""
    loader = MerchantDataLoader(redis_client)
    await loader.load()
    await redis_client.redis.hset(RedisKeys.merchant_inventory(7), "slot_1", "15:1")
    await loader.initialize(force_clear=False)
    assert await redis_client.redis.hget(RedisKeys.merchant_inventory(7), "slot_1") == "15:1"


@pytest.mark.asyncio
async def test_merchant_loader_initialize_with_force_clear(
    redis_client: RedisClient,
) -> None:
    """Sólo un restablecimiento explícito vuelve a usar la semilla."""
    loader = MerchantDataLoader(redis_client)
    await loader.load()
    initial = await redis_client.redis.hgetall(RedisKeys.merchant_inventory(7))
    await redis_client.redis.hset(RedisKeys.merchant_inventory(7), "slot_1", "15:1")
    await loader.initialize(force_clear=True)
    assert await redis_client.redis.hgetall(RedisKeys.merchant_inventory(7)) == initial


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

    keys = [key async for key in redis_client.redis.scan_iter(match="merchant:*:inventory")]
    assert len(keys) >= 10
