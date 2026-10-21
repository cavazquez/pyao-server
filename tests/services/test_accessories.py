"""Accesorios reales: ranura única, restricciones y efectos derivados al combatir."""

from unittest.mock import AsyncMock, patch

import pytest

from src.models.character_class import ClassCatalog
from src.services.combat.physical_plan import PhysicalPlan, PhysicalRequest, commit_physical
from src.services.combat.pvp_policy import PvpPolicy
from src.services.combat.spell_plan import CastRequest, SpellPlan, commit_spell
from src.services.player.accessories import toggle_accessory
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_all_accessories_replace_without_accumulating_and_enforce_classes(mechanics_world):
    """Los doce IDs son equipables sólo por las clases indicadas en su catálogo."""
    w = mechanics_world
    for item_id in w.catalog.get_all_item_ids():
        item = w.catalog.get_item_data(item_id)
        if item["ObjType"] != 18:
            continue
        forbidden = item.get("ClasesProhibidas", [])
        allowed = next(
            c for c in ClassCatalog().get_all_classes() if c.name.upper() not in forbidden
        )
        await w.redis.hset(RedisKeys.player_user_stats(1), "class_id", allowed.class_id)
        await w.redis.hset(
            RedisKeys.player_inventory(1), mapping={"slot_1": f"{item_id}:1", "slot_2": "700:1"}
        )
        assert (await toggle_accessory(w.redis, 1, 1))["equipped"]
        assert (await toggle_accessory(w.redis, 1, 2))["equipped"]
        assert await w.redis.hget(RedisKeys.player_equipment(1), "accessory") == "2"
        assert not (await toggle_accessory(w.redis, 1, 2))["equipped"]
        assert await w.redis.hget(RedisKeys.player_equipment(1), "accessory") == "0"
        if forbidden:
            rejected = next(
                c for c in ClassCatalog().get_all_classes() if c.name.upper() in forbidden
            )
            await w.redis.hset(RedisKeys.player_user_stats(1), "class_id", rejected.class_id)
            assert not (await toggle_accessory(w.redis, 1, 1))["applied"]
            assert await w.redis.hget(RedisKeys.player_equipment(1), "accessory") == "0"


@pytest.mark.asyncio
async def test_ring_reduces_magic_once_and_unequip_restores_original_damage(mechanics_world):
    """No se modifica la base del personaje ni se vuelve a cobrar un replay."""
    w = mechanics_world
    await w.redis.hset(RedisKeys.player_spellbook(1), "1", 2)
    await w.redis.hset(RedisKeys.player_user_stats(2), "class_id", 2)
    await w.redis.hset(RedisKeys.player_inventory(2), "slot_1", "697:1")
    hp = []
    for equipped in (False, True, False):
        await w.redis.hset(
            RedisKeys.player_user_stats(1), mapping={"min_mana": 100, "min_sta": 100}
        )
        await w.redis.hset(RedisKeys.player_user_stats(2), "min_hp", 500)
        if equipped or len(hp) == 2:
            assert (await toggle_accessory(w.redis, 2, 1))["applied"]
        plan = SpellPlan(
            CastRequest(1, 2, 50, 51, 1, 2),
            {"min_damage": 20, "max_damage": 20, "mana_cost": 10},
            PvpPolicy(),
        )
        plan.item_catalog = w.catalog
        identity = operation_id()
        with patch("src.services.combat.spell_plan.require_durable", new=AsyncMock()):
            result = await commit_spell(w.redis.redis, identity, plan)
            assert result["applied"], result
            assert await commit_spell(w.redis.redis, identity, plan) == result
        hp.append(int(await w.redis.hget(RedisKeys.player_user_stats(2), "min_hp")))
        assert await w.redis.hget(RedisKeys.player_user_stats(1), "min_mana") == "90"
    assert hp[0] == hp[2]
    assert hp[1] - hp[0] == 5  # Anillo 697: resistencia 4/6, media entera 5.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("item_id", "accepted"),
    [
        (208, True),
        (696, True),
        (1049, True),
        (1050, True),
        (863, False),
        (864, False),
        (697, False),
    ],
)
async def test_only_declared_focus_power_satisfies_staff_requirement(
    mechanics_world, item_id, accepted
):
    """Un foco equipado puede reemplazar al bastón; un anillo no lo suplanta."""
    w = mechanics_world
    await w.redis.hset(RedisKeys.player_spellbook(1), "1", 2)
    await w.redis.hset(RedisKeys.player_inventory(1), "slot_1", f"{item_id}:1")
    await w.redis.hset(RedisKeys.player_equipment(1), "accessory", 1)
    plan = SpellPlan(
        CastRequest(1, 2, 51, 50, 1, target_npc="animal"),
        {"min_damage": 5, "max_damage": 5, "need_staff": True},
        PvpPolicy(),
    )
    plan.staff_items = w.catalog.staff_item_ids()
    with patch("src.services.combat.spell_plan.require_durable", new=AsyncMock()):
        assert (await commit_spell(w.redis.redis, operation_id(), plan))["applied"] is accepted


@pytest.mark.asyncio
async def test_gloves_only_change_unarmed_damage_not_weapon_or_base_attributes(mechanics_world):
    """Los guantes de lucha se derivan del slot actual, sin acumular stats."""
    w = mechanics_world
    attrs = await w.redis.hgetall(RedisKeys.player_stats(1))
    await w.redis.hset(
        RedisKeys.player_inventory(1), mapping={"slot_1": "1036:1", "slot_2": "15:1"}
    )
    results = []
    for weapon, glove in ((False, False), (False, True), (True, True), (True, False)):
        await w.redis.hset(
            RedisKeys.player_equipment(1),
            mapping={"weapon": "2" if weapon else "0", "accessory": "1" if glove else "0"},
        )
        await w.redis.hset(RedisKeys.npc_instance("animal"), "hp", 500)
        with patch(
            "src.services.combat.physical_plan.random.random",
            side_effect=[0.0, 0.99, 0.99, 0.5, 0.99],
        ):
            plan = PhysicalPlan(PhysicalRequest(1, target_npc="animal"), w.catalog, 30, 20)
        result = await commit_physical(w.redis.redis, plan, operation_id())
        assert result["applied"], result
        results.append(result["damage"])
    assert results[1] > results[0]
    assert results[2] == results[3]
    assert await w.redis.hgetall(RedisKeys.player_stats(1)) == attrs
