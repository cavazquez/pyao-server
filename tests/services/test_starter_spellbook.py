"""El login es lectura de progreso, no una entrega repetible de recursos."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.command_handlers.login_initialization_handler import LoginInitializationHandler
from src.config.config_manager import config_manager
from src.models.spell_catalog import SpellCatalog
from src.repositories.account_repository import AccountRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.repositories.spellbook_repository import SpellbookRepository
from src.services.player.player_service import PlayerService
from src.services.starter_spellbook import initialize_starter_spellbook


@pytest.mark.asyncio
async def test_starter_seed_is_once_and_login_preserves_sparse_order(redis_client):
    """Catálogo nuevo, borrar un slot y reconectar no enseñan hechizos automáticamente."""
    book, catalog = SpellbookRepository(redis_client), SpellCatalog()
    await asyncio.gather(*(initialize_starter_spellbook(book, 1, 1, catalog) for _ in range(5)))
    assert await book.get_all_spells(1) == {1: 2, 2: 3}
    await book.clear_spellbook(1)
    await book.add_spell(1, 9, 3)
    await book.add_spell(1, 30, 2)
    before = await redis_client.hgetall("player:1:spellbook")
    sender = MagicMock()
    sender.send_change_spell_slot = AsyncMock()
    handler = LoginInitializationHandler(
        PlayerRepository(redis_client), AccountRepository(redis_client), book, catalog, sender
    )
    await handler.send_spellbook(1)
    await handler.send_spellbook(1)
    await initialize_starter_spellbook(book, 1, 1, catalog)
    assert await redis_client.hgetall("player:1:spellbook") == before
    assert await book.get_all_spells(1) == {9: 3, 30: 2}
    assert sender.send_change_spell_slot.await_count == 4


@pytest.mark.asyncio
async def test_starter_config_is_explicit_by_class_and_empty_is_stable(redis_client):
    """Una clase puede empezar sin libro sin que un login posterior lo rellene."""
    book, catalog = SpellbookRepository(redis_client), SpellCatalog()
    with patch.object(config_manager, "get_section", return_value={"1": [3], "12": []}):
        await initialize_starter_spellbook(book, 1, 1, catalog)
        await initialize_starter_spellbook(book, 2, 12, catalog)
    assert await book.get_all_spells(1) == {1: 3}
    assert await book.get_all_spells(2) == {}
    await initialize_starter_spellbook(book, 2, 12, catalog)
    assert await book.get_all_spells(2) == {}


@pytest.mark.asyncio
async def test_reading_inventory_does_not_mint_boats(redis_client):
    """Vender/dropear una barca y reconectar no crea otra para venderla de nuevo."""
    repo = PlayerRepository(redis_client)
    service = PlayerService(repo, MagicMock(), AccountRepository(redis_client))
    inventory = InventoryRepository(redis_client)
    await service.send_inventory(1)
    await service.send_inventory(1)
    assert not await inventory.get_inventory_slots(1)
