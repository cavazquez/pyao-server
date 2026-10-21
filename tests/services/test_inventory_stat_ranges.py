"""La defensa máxima no se pierde al pasar del catálogo al inventario/banco/UI."""

from unittest.mock import AsyncMock

import pytest

from src.models.item import Item, ItemType
from src.models.item_catalog import ItemCatalog
from src.models.items_catalog import ITEMS_CATALOG
from src.repositories.bank_repository import BankRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.combat.physical_plan import defense
from src.services.inventory_notifications import notify_bank, notify_inventory
from src.services.player.player_service import PlayerService
from src.utils.redis_config import RedisKeys


def test_entire_catalog_preserves_distinct_defense_limits():
    """Contrasta todos los IDs con los valores originales, no con otro valor derivado."""
    catalog = ItemCatalog()
    for item_id in catalog.get_all_item_ids():
        raw = catalog.get_item_data(item_id)
        item = ITEMS_CATALOG[item_id]
        assert (item.defense or 0) == raw.get(
            "DefensaMagicaMin" if raw["ObjType"] == 18 else "MinDef", 0
        ), item_id
        assert (item.max_defense or 0) == raw.get(
            "DefensaMagicaMax" if raw["ObjType"] == 18 else "MaxDef", 0
        ), item_id
        assert item.to_client_type() == raw["ObjType"], item_id


def test_hand_created_items_keep_their_single_defense_value():
    """Los objetos construidos directamente siguen admitiendo defensa uniforme."""
    item = Item(1, "Fixture", ItemType.ARMOR, 1, defense=10)
    assert item.max_defense == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("item_id", [30, 128, 131, 882, 1081, 1082])
async def test_pickup_login_and_bank_publish_the_real_defense_range(redis_client, item_id):
    """La armadura o escudo conserva MinDef/MaxDef tras recoger y volver a entrar."""
    raw = ItemCatalog().get_item_data(item_id)
    inventory = InventoryRepository(redis_client)
    await inventory.set_slot(1, 1, item_id, 1)
    sender = AsyncMock()
    await notify_inventory(sender, inventory, 1)
    first = sender.send_change_inventory_slot.await_args_list[0].kwargs
    assert (first["min_def"], first["max_def"]) == (raw["MinDef"], raw["MaxDef"])
    assert first["item_type"] == raw["ObjType"]
    sender.reset_mock()
    await PlayerService(PlayerRepository(redis_client), sender).send_inventory(1)
    first = sender.send_change_inventory_slot.await_args_list[0].kwargs
    assert (first["min_def"], first["max_def"]) == (raw["MinDef"], raw["MaxDef"])
    assert first["item_type"] == raw["ObjType"]
    sender.reset_mock()
    bank = BankRepository(redis_client)
    await redis_client.hset(RedisKeys.bank(1), "slot_1", f"{item_id}:1")
    await notify_bank(sender, bank, 1)
    first = sender.send_change_bank_slot.await_args_list[0].kwargs
    assert (first["min_def"], first["max_def"]) == (raw["MinDef"], raw["MaxDef"])
    assert first["item_type"] == raw["ObjType"]


@pytest.mark.parametrize(("item_id", "expected"), [(30, 78), (481, 50)])
def test_looted_armor_reduces_actual_physical_damage(item_id, expected):
    """La armadura superior del catálogo reduce efectivamente más un golpe idéntico."""
    snapshot = {
        RedisKeys.player_equipment(1): {"armor": "1"},
        RedisKeys.player_inventory(1): {"slot_1": f"{item_id}:1"},
        RedisKeys.player_skills(1): {},
        RedisKeys.player_stats(1): {},
        RedisKeys.player_user_stats(1): {},
    }
    damage, dodged, blocked, _events = defense(snapshot, 1, ItemCatalog(), 100, 1.0, 1.0, {})
    assert not dodged
    assert not blocked
    assert damage == expected


def test_better_shield_and_equipped_helmet_change_real_defense():
    """Los stats no se limitan a la etiqueta: mejor escudo bloquea y el casco mitiga."""
    snapshot = {
        RedisKeys.player_equipment(1): {"shield": "1"},
        RedisKeys.player_inventory(1): {"slot_1": "404:1", "slot_2": "405:1"},
        RedisKeys.player_skills(1): {},
        RedisKeys.player_stats(1): {},
        RedisKeys.player_user_stats(1): {"class_id": "3"},
    }
    catalog = ItemCatalog()
    weak = defense(snapshot, 1, catalog, 100, 1.0, 0.05, {})
    snapshot[RedisKeys.player_inventory(1)]["slot_1"] = "1082:1"
    strong = defense(snapshot, 1, catalog, 100, 1.0, 0.05, {})
    assert not weak[2]
    assert strong[2]
    assert strong[0] == 0 < weak[0]
    snapshot[RedisKeys.player_equipment(1)] = {"helmet": "2"}
    helmet = defense(snapshot, 1, catalog, 100, 1.0, 1.0, {})
    assert helmet[0] < weak[0]
    assert not helmet[2]
