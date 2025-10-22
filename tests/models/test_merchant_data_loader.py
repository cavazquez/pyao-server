"""Tests para MerchantDataLoader."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.merchant_data_loader import MerchantDataLoader
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys


@pytest.fixture
def redis_client() -> RedisClient:
    """Fixture para crear un cliente Redis mockeado."""
    client = MagicMock(spec=RedisClient)
    client.redis = MagicMock()
    client.redis.hset = AsyncMock()
    client.redis.delete = AsyncMock()
    return client


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
    assert loader.TOML_FILE == "data/merchant_inventories.toml"


@pytest.mark.asyncio
async def test_merchant_loader_load_success(redis_client: RedisClient) -> None:
    """Verifica que load() carga los inventarios correctamente."""
    loader = MerchantDataLoader(redis_client)

    # Verificar que el archivo TOML existe
    toml_path = Path(loader.TOML_FILE)
    assert toml_path.exists(), f"Archivo {loader.TOML_FILE} no encontrado"  # noqa: ASYNC240

    # Ejecutar load
    await loader.load()

    # Verificar que se llamó hset para cargar items
    assert redis_client.redis.hset.called
    assert redis_client.redis.hset.call_count > 0


@pytest.mark.asyncio
async def test_merchant_loader_load_creates_correct_keys(redis_client: RedisClient) -> None:
    """Verifica que load() crea las keys correctas en Redis."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    # Verificar que se creó la key del Comerciante (npc_id=2)
    expected_key = RedisKeys.merchant_inventory(2)
    calls = redis_client.redis.hset.call_args_list

    # Verificar que al menos una llamada usó la key correcta
    keys_used = {call[0][0] for call in calls}
    assert expected_key in keys_used


@pytest.mark.asyncio
async def test_merchant_loader_load_correct_format(redis_client: RedisClient) -> None:
    """Verifica que load() usa el formato correcto item_id:quantity."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    # Verificar formato de los valores
    calls = redis_client.redis.hset.call_args_list
    for call in calls:
        value = call[0][2]  # Tercer argumento es el value
        # Debe tener formato "item_id:quantity"
        assert ":" in value
        parts = value.split(":")
        assert len(parts) == 2
        assert parts[0].isdigit()  # item_id es número
        assert parts[1].isdigit()  # quantity es número


@pytest.mark.asyncio
async def test_merchant_loader_clear(redis_client: RedisClient) -> None:
    """Verifica que clear() limpia los inventarios."""
    loader = MerchantDataLoader(redis_client)

    await loader.clear()

    # Verificar que se llamó delete
    assert redis_client.redis.delete.called


@pytest.mark.asyncio
async def test_merchant_loader_clear_deletes_correct_keys(redis_client: RedisClient) -> None:
    """Verifica que clear() elimina las keys correctas."""
    loader = MerchantDataLoader(redis_client)

    await loader.clear()

    # Verificar que se eliminó la key del Comerciante (npc_id=2)
    expected_key = RedisKeys.merchant_inventory(2)
    calls = redis_client.redis.delete.call_args_list

    keys_deleted = {call[0][0] for call in calls}
    assert expected_key in keys_deleted


@pytest.mark.asyncio
async def test_merchant_loader_initialize_without_force_clear(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize() sin force_clear solo carga datos."""
    loader = MerchantDataLoader(redis_client)

    await loader.initialize(force_clear=False)

    # Debe haber llamado hset (load)
    assert redis_client.redis.hset.called

    # NO debe haber llamado delete (clear)
    assert not redis_client.redis.delete.called


@pytest.mark.asyncio
async def test_merchant_loader_initialize_with_force_clear(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize() con force_clear limpia y luego carga."""
    loader = MerchantDataLoader(redis_client)

    await loader.initialize(force_clear=True)

    # Debe haber llamado delete (clear)
    assert redis_client.redis.delete.called

    # Debe haber llamado hset (load)
    assert redis_client.redis.hset.called


@pytest.mark.asyncio
async def test_merchant_loader_handles_missing_file() -> None:
    """Verifica que load() maneja correctamente un archivo faltante."""
    redis_client = MagicMock(spec=RedisClient)
    redis_client.redis = MagicMock()
    redis_client.redis.hset = AsyncMock()

    loader = MerchantDataLoader(redis_client)
    loader.TOML_FILE = "data/nonexistent_file.toml"

    # No debe lanzar excepción
    await loader.load()

    # No debe haber intentado cargar nada
    assert not redis_client.redis.hset.called


@pytest.mark.asyncio
async def test_merchant_loader_loads_multiple_merchants(redis_client: RedisClient) -> None:
    """Verifica que load() puede cargar múltiples mercaderes si existen."""
    loader = MerchantDataLoader(redis_client)

    await loader.load()

    # Verificar que se cargó al menos el Comerciante
    # (En el futuro podría haber más mercaderes)
    assert redis_client.redis.hset.call_count >= 10  # Al menos 10 items del Comerciante
