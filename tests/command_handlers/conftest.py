"""Fixtures de recursos concretos para los handlers de suelo persistido."""

from unittest.mock import AsyncMock, patch

import pytest_asyncio

from src.game.map_manager import MapManager
from src.models.item_catalog import ItemCatalog
from src.repositories.ground_items_repository import GroundItemsRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository


@pytest_asyncio.fixture
async def ground_world(redis_client):
    """Comparte Redis realista, índice persistido y emisores de prueba.

    Yields:
        Redis, jugador, inventario, suelo, mapa, catálogo, emisor y broadcast.
    """
    player = PlayerRepository(redis_client)
    inventory = InventoryRepository(redis_client)
    ground = GroundItemsRepository(redis_client)
    manager = MapManager(ground)
    for user_id in [1, 2]:
        await player.set_position(user_id, 50, 50, 1)
        await player.set_stats(user_id, 100, 100, 100, 100, 100, 100, 100, 1, 300, 0)
    sender, broadcast = AsyncMock(), AsyncMock()
    with (
        patch("src.services.ground_transfer.require_durable", new=AsyncMock()),
        patch("src.repositories.ground_items_repository.require_durable", new=AsyncMock()),
    ):
        yield redis_client, player, inventory, ground, manager, ItemCatalog(), sender, broadcast
