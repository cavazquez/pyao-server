"""Tests para InventoryRepository."""

from unittest.mock import MagicMock

import pytest

from src.inventory_repository import InventoryRepository


@pytest.mark.asyncio
class TestInventoryRepository:
    """Tests para InventoryRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        repo = InventoryRepository(redis_client)

        assert repo.redis_client == redis_client
