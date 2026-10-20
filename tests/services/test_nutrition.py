"""Todos los alimentos y bebidas del catálogo consumen una unidad y restauran sus valores."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.commands.use_item_command import UseItemCommand
from src.models.item_catalog import ItemCatalog
from src.models.item_types import ObjType
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.nutrition import NutritionRule, consume_nutrition
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys

CATALOG = ItemCatalog()
CONSUMABLES = [
    i
    for i in CATALOG.get_all_item_ids()
    if CATALOG.get_item_data(i)["ObjType"]
    in {ObjType.COMIDA, ObjType.BEBIDA, ObjType.BOTELLAS_LLENAS}
]


async def seed(client, item_id, *, quantity=2):
    """Prepara únicamente recursos anteriores a la acción, con necesidades bajas."""
    await client.hset(RedisKeys.player_inventory(1), "slot_1", f"{item_id}:{quantity}")
    await client.hset(
        RedisKeys.player_user_stats(1),
        mapping={"min_hp": "20", "max_hp": "100", "min_sta": "10", "max_sta": "100"},
    )
    await client.hset(
        RedisKeys.player_hunger_thirst(1),
        mapping={
            "min_hunger": "0",
            "max_hunger": "100",
            "min_water": "0",
            "max_water": "100",
            "hunger_flag": "1",
            "thirst_flag": "1",
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("item_id", CONSUMABLES)
async def test_all_catalog_food_and_drinks_use_their_real_effects(
    redis_client, monkeypatch, item_id
):
    """Incluye peces, pan, alcohol, manzanas con otros IDs y el odre lleno."""
    monkeypatch.setattr("src.services.nutrition.require_durable", AsyncMock())
    await seed(redis_client, item_id)
    raw = CATALOG.get_item_data(item_id)
    rule = NutritionRule.from_item(item_id, raw)
    identity = operation_id()
    first = await consume_nutrition(redis_client.redis, 1, 1, identity, rule, 30, 20)
    assert first["applied"]
    assert await consume_nutrition(redis_client.redis, 1, 1, identity, rule, 30, 20) == first
    assert await redis_client.hget(RedisKeys.player_inventory(1), "slot_1") == f"{item_id}:1"
    needs = await redis_client.hgetall(RedisKeys.player_hunger_thirst(1))
    stats = await redis_client.hgetall(RedisKeys.player_user_stats(1))
    assert int(needs["min_hunger"]) == min(100, rule.hunger)
    assert int(needs["min_water"]) == min(100, rule.water)
    assert int(stats["min_hp"]) == min(100, 20 + rule.hp)
    assert int(stats["min_sta"]) == min(100, 10 + rule.stamina)
    assert needs["hunger_flag"] == ("0" if rule.hunger else "1")
    assert needs["thirst_flag"] == ("0" if rule.water else "1")
    if rule.empty_item:
        assert "534:1" in (await redis_client.hgetall(RedisKeys.player_inventory(1))).values()


@pytest.mark.asyncio
async def test_two_uses_of_last_food_do_not_duplicate_effects(redis_client, monkeypatch):
    """Dos comandos nuevos que compiten por el mismo pez sólo restauran una vez."""
    monkeypatch.setattr("src.services.nutrition.require_durable", AsyncMock())
    await seed(redis_client, 139, quantity=1)
    rule = NutritionRule.from_item(139, CATALOG.get_item_data(139))
    results = await asyncio.gather(
        *(
            consume_nutrition(redis_client.redis, 1, 1, operation_id(), rule, 30, 20)
            for _ in range(2)
        )
    )
    assert sum(row["applied"] for row in results) == 1
    assert await redis_client.hget(RedisKeys.player_hunger_thirst(1), "min_hunger") == "75"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["dead", "changed", "full_waterskin"])
async def test_invalid_consumption_does_not_lose_the_item(redis_client, monkeypatch, kind):
    """No resucita con comida, consume otro ID ni pierde un envase sin espacio."""
    monkeypatch.setattr("src.services.nutrition.require_durable", AsyncMock())
    item_id = 533 if kind == "full_waterskin" else 1
    await seed(redis_client, item_id)
    if kind == "dead":
        await redis_client.hset(RedisKeys.player_user_stats(1), "min_hp", "0")
    if kind == "changed":
        await redis_client.hset(RedisKeys.player_inventory(1), "slot_1", "15:1")
    before = await redis_client.hgetall(RedisKeys.player_inventory(1))
    result = await consume_nutrition(
        redis_client.redis,
        1,
        1,
        operation_id(),
        NutritionRule.from_item(item_id, CATALOG.get_item_data(item_id)),
        1 if kind == "full_waterskin" else 30,
        20,
    )
    assert not result["applied"]
    assert await redis_client.hgetall(RedisKeys.player_inventory(1)) == before
    assert await redis_client.hget(RedisKeys.player_hunger_thirst(1), "min_water") == "0"


@pytest.mark.asyncio
async def test_use_item_routes_a_fish_through_real_inventory_and_updates(redis_client, monkeypatch):
    """Comprueba el camino que antes sólo reconocía la manzana de ID 1."""
    monkeypatch.setattr("src.services.nutrition.require_durable", AsyncMock())
    await seed(redis_client, 544, quantity=1)
    sender = AsyncMock()
    player = PlayerRepository(redis_client)
    handler = UseItemCommandHandler(player, None, None, sender, item_catalog=CATALOG)
    result = await handler.handle(UseItemCommand(1, 1))
    assert result.success
    assert result.data["handled"]
    assert await InventoryRepository(redis_client).get_slot(1, 1) is None
    assert (await player.get_hunger_thirst(1))["min_hunger"] == 75
    sender.send_update_hunger_and_thirst.assert_awaited_once_with(
        max_water=100, min_water=0, max_hunger=100, min_hunger=75
    )


@pytest.mark.parametrize(
    "raw", [{"ObjType": 2}, {"ObjType": 1, "MinHam": -1}, {"ObjType": 13, "MinAgu": 1001}]
)
def test_invalid_nutrition_rules_are_rejected(raw):
    """Una regla inválida no empieza a mutar un inventario."""
    with pytest.raises(ValueError, match="efectos válidos"):
        NutritionRule.from_item(1, raw)
