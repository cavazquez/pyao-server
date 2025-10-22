"""Tests para DataInitializer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.data_initializer import DataInitializer
from src.utils.base_data_loader import BaseDataLoader
from src.utils.redis_client import RedisClient


class MockLoader(BaseDataLoader):
    """Loader mock para testing."""

    def __init__(self, redis_client: RedisClient, name: str = "Mock Loader") -> None:
        """Inicializa el mock loader.

        Args:
            redis_client: Cliente de Redis.
            name: Nombre del loader.
        """
        super().__init__(redis_client)
        self._name = name
        self.load_called = False
        self.clear_called = False

    def get_name(self) -> str:
        """Retorna el nombre del loader."""
        return self._name

    async def load(self) -> None:
        """Mock de load."""
        self.load_called = True

    async def clear(self) -> None:
        """Mock de clear."""
        self.clear_called = True


@pytest.fixture
def redis_client() -> RedisClient:
    """Fixture para crear un cliente Redis mockeado."""
    client = MagicMock(spec=RedisClient)
    client.redis = MagicMock()
    return client


@pytest.mark.asyncio
async def test_data_initializer_initialization(redis_client: RedisClient) -> None:
    """Verifica que DataInitializer se inicializa correctamente."""
    initializer = DataInitializer(redis_client)

    assert initializer.redis_client is redis_client
    assert len(initializer.loaders) > 0  # Debe tener al menos MerchantDataLoader


@pytest.mark.asyncio
async def test_data_initializer_has_merchant_loader(redis_client: RedisClient) -> None:
    """Verifica que DataInitializer incluye MerchantDataLoader."""
    initializer = DataInitializer(redis_client)

    loader_names = [loader.get_name() for loader in initializer.loaders]
    assert "Merchant Inventories" in loader_names


@pytest.mark.asyncio
async def test_data_initializer_list_loaders(redis_client: RedisClient) -> None:
    """Verifica que list_loaders() retorna los nombres correctos."""
    initializer = DataInitializer(redis_client)

    loader_names = initializer.list_loaders()

    assert isinstance(loader_names, list)
    assert len(loader_names) > 0
    assert "Merchant Inventories" in loader_names


@pytest.mark.asyncio
async def test_data_initializer_initialize_all_without_force_clear(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize_all() ejecuta todos los loaders sin clear."""
    # Crear initializer con loaders mock
    initializer = DataInitializer(redis_client)
    mock_loader1 = MockLoader(redis_client, "Loader 1")
    mock_loader2 = MockLoader(redis_client, "Loader 2")
    initializer.loaders = [mock_loader1, mock_loader2]

    await initializer.initialize_all(force_clear=False)

    # Verificar que load fue llamado en ambos
    assert mock_loader1.load_called
    assert mock_loader2.load_called

    # Verificar que clear NO fue llamado
    assert not mock_loader1.clear_called
    assert not mock_loader2.clear_called


@pytest.mark.asyncio
async def test_data_initializer_initialize_all_with_force_clear(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize_all() con force_clear limpia antes de cargar."""
    initializer = DataInitializer(redis_client)
    mock_loader = MockLoader(redis_client)
    initializer.loaders = [mock_loader]

    await initializer.initialize_all(force_clear=True)

    # Verificar que clear fue llamado
    assert mock_loader.clear_called

    # Verificar que load fue llamado
    assert mock_loader.load_called


@pytest.mark.asyncio
async def test_data_initializer_initialize_specific_success(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize_specific() ejecuta el loader correcto."""
    initializer = DataInitializer(redis_client)
    mock_loader1 = MockLoader(redis_client, "Loader 1")
    mock_loader2 = MockLoader(redis_client, "Loader 2")
    initializer.loaders = [mock_loader1, mock_loader2]

    result = await initializer.initialize_specific("Loader 2", force_clear=False)

    # Debe retornar True
    assert result is True

    # Solo loader2 debe haber sido ejecutado
    assert not mock_loader1.load_called
    assert mock_loader2.load_called


@pytest.mark.asyncio
async def test_data_initializer_initialize_specific_not_found(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize_specific() retorna False si no encuentra el loader."""
    initializer = DataInitializer(redis_client)
    mock_loader = MockLoader(redis_client, "Loader 1")
    initializer.loaders = [mock_loader]

    result = await initializer.initialize_specific("Nonexistent Loader", force_clear=False)

    # Debe retornar False
    assert result is False

    # Ningún loader debe haber sido ejecutado
    assert not mock_loader.load_called


@pytest.mark.asyncio
async def test_data_initializer_initialize_specific_case_insensitive(
    redis_client: RedisClient,
) -> None:
    """Verifica que initialize_specific() es case-insensitive."""
    initializer = DataInitializer(redis_client)
    mock_loader = MockLoader(redis_client, "Mock Loader")
    initializer.loaders = [mock_loader]

    result = await initializer.initialize_specific("mock loader", force_clear=False)

    # Debe encontrar el loader (case-insensitive)
    assert result is True
    assert mock_loader.load_called


@pytest.mark.asyncio
async def test_data_initializer_loaders_execute_in_order(
    redis_client: RedisClient,
) -> None:
    """Verifica que los loaders se ejecutan en el orden definido."""
    initializer = DataInitializer(redis_client)

    execution_order: list[str] = []

    class OrderedMockLoader(BaseDataLoader):
        def __init__(self, redis_client: RedisClient, name: str) -> None:
            super().__init__(redis_client)
            self._name = name

        def get_name(self) -> str:
            return self._name

        async def load(self) -> None:
            execution_order.append(self._name)

    loader1 = OrderedMockLoader(redis_client, "First")
    loader2 = OrderedMockLoader(redis_client, "Second")
    loader3 = OrderedMockLoader(redis_client, "Third")

    initializer.loaders = [loader1, loader2, loader3]

    await initializer.initialize_all(force_clear=False)

    # Verificar orden de ejecución
    assert execution_order == ["First", "Second", "Third"]


@pytest.mark.asyncio
async def test_data_initializer_with_real_merchant_loader(
    redis_client: RedisClient,
) -> None:
    """Verifica que DataInitializer funciona con el MerchantDataLoader real."""
    redis_client.redis.hset = AsyncMock()
    redis_client.redis.delete = AsyncMock()

    initializer = DataInitializer(redis_client)

    # No debe lanzar excepción
    await initializer.initialize_all(force_clear=False)

    # Debe haber cargado datos
    assert redis_client.redis.hset.called
