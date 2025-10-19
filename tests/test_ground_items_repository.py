"""Tests básicos para GroundItemsRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ground_items_repository import GroundItemsRepository


@pytest.mark.asyncio
class TestGroundItemsRepository:
    """Tests básicos para GroundItemsRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        repo = GroundItemsRepository(redis_client)

        assert repo.redis_client == redis_client

    async def test_add_ground_item(self) -> None:
        """Test de agregar item al suelo (test básico)."""
        redis_client = MagicMock()
        redis_client.get = AsyncMock(return_value=None)
        redis_client.set = AsyncMock()

        repo = GroundItemsRepository(redis_client)
        item = {"item_id": 10, "quantity": 5}

        # Solo verificar que no crashea
        await repo.add_ground_item(map_id=1, x=50, y=50, item=item)
