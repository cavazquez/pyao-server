"""Acciones reales: costes, poder, entrenamiento y replays sobre Redis."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.items.ledger import PREFIX
from src.items.migration import migrate as migrate_items
from src.models.crafting_data_loader import CRAFTING_KEY, load_recipes
from src.models.items_catalog import ITEMS_CATALOG
from src.models.skill_data_loader import SKILL_RULES_KEY
from src.repositories.clan_repository import ClanRepository
from src.repositories.merchant_repository import MerchantRepository
from src.repositories.party_repository import PartyRepository
from src.services.clan_service import ClanService
from src.services.combat.physical_plan import (
    PhysicalPlan,
    PhysicalRequest,
    commit_physical,
    defend_npc,
)
from src.services.commerce_service import CommerceService
from src.services.crafting import craft
from src.services.gathering import GATHERING, gather
from src.services.meditation import meditate_tick
from src.services.navigation import navigate
from src.services.npc_trade_plan import commerce_price
from src.services.party_service import PartyService
from src.services.personal_skills import hide, steal, survival, tame
from src.utils.gold_atomic import operation_id
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_id", [9, 12, 13])
@pytest.mark.parametrize("success", [True, False])
async def test_gathering_attempt_is_atomic_and_replay_does_not_train_twice(
    mechanics_world, skill_id, success
):
    """Talar, pescar y minar entrenan sólo después de validar recurso y herramienta."""
    world = mechanics_world
    world.terrain.has_water = lambda *_: True
    skill, tool, item_id, quantity, _name, _roll = GATHERING[skill_id]
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", f"{tool}:1")
    await world.redis.hset(RedisKeys.player_equipment(1), "weapon", "1")
    identity = operation_id()
    with patch("src.services.gathering.random.random", return_value=0.0 if success else 0.99):
        first = await gather(
            world.player, world.inventory, world.terrain, 1, skill_id, 2, 51, 50, identity=identity
        )
        again = await gather(
            world.player, world.inventory, world.terrain, 1, skill_id, 2, 51, 50, identity=identity
        )
    assert first == again
    assert first["successful"] is success
    assert first["quantity"] == (quantity if success else 0)
    assert await world.redis.hget(RedisKeys.player_skills(1), f"xp:{skill}") == (
        "50" if success else "20"
    )
    assert sum(
        s.quantity
        for s in (await world.inventory.get_inventory_slots(1)).values()
        if s.item_id == item_id
    ) == (quantity if success else 0)


@pytest.mark.asyncio
async def test_invalid_gathering_cannot_farm_xp_or_create_resources(mechanics_world):
    """No hay progreso con muerte, distancia, terreno inexistente o herramienta ausente."""
    world = mechanics_world
    saved = await world.redis.hgetall(RedisKeys.player_skills(1))
    for x in (0, 52, 51):
        result = await gather(world.player, world.inventory, world.terrain, 1, 9, 2, x, 50)
        assert result["applied"] is False
    assert await world.redis.hgetall(RedisKeys.player_skills(1)) == saved


def test_all_owned_recipes_have_real_materials_and_preserve_carpentry():
    """Los tres catálogos se cargan y ningún índice interno se interpreta como objeto."""
    rows = load_recipes()
    assert len([r for r in rows if r["skill"] == "herreria"]) == 87
    assert len([r for r in rows if r["skill"] == "carpinteria"]) == 34
    assert len([r for r in rows if r["skill"] == "mineria"]) == 3
    dagger = next(r for r in rows if r["id"] == "herreria:15")
    assert dagger["materials"] == [{"item_id": 386, "quantity": 2}]
    assert dagger["required"] == 10


@pytest.mark.asyncio
@pytest.mark.parametrize("recipe_id", ["herreria:15", "carpinteria:480", "fundir:192"])
@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("individual", [True, False])
async def test_crafting_confirms_actual_materials_product_and_training(
    mechanics_world, recipe_id, success, individual
):
    """Fabricar y fundir no duplican materiales, productos ni XP ante un reintento."""
    world = mechanics_world
    recipe = next(
        r for r in json.loads(await world.redis.get(CRAFTING_KEY)) if r["id"] == recipe_id
    )
    if recipe["success_rate"] == 100 and not success:
        return
    await world.redis.hset(RedisKeys.player_skills(1), f"level:{recipe['skill']}", "30")
    tool = 565 if recipe["skill"] == "herreria" else 564
    await world.redis.hset(
        RedisKeys.player_inventory(1),
        mapping={"slot_1": f"{tool}:1", "slot_2": f"{recipe['materials'][0]['item_id']}:20"},
    )
    iid = ""
    if individual:
        await migrate_items(world.redis.redis)
        iid = InventorySlot.parse(
            await world.redis.hget(RedisKeys.player_inventory(1), "slot_1")
        ).instance_ids[0]
    identity = operation_id()
    with patch("src.services.crafting.random.random", return_value=0.0 if success else 0.999):
        first = await craft(
            world.player, world.inventory, world.terrain, 1, recipe_id, 2, identity=identity
        )
        saved = await world.inventory.get_inventory(1)
        second = await craft(
            world.player, world.inventory, world.terrain, 1, recipe_id, 2, identity=identity
        )
    assert first == second
    assert first["successful"] is success
    assert await world.inventory.get_inventory(1) == saved
    assert await world.redis.hget(RedisKeys.player_skills(1), f"xp:{recipe['skill']}") == (
        "50" if success else "20"
    )
    product = sum(
        s.quantity
        for s in (await world.inventory.get_inventory_slots(1)).values()
        if s.item_id == recipe["item_id"]
    )
    assert product == (2 if success else 0)

    if iid:
        assert await world.redis.hget(PREFIX + iid, "uses_spent") == (
            "0" if recipe["skill"] == "mineria" else "2"
        )


@pytest.mark.asyncio
async def test_crafting_rejects_missing_tool_materials_station_and_forged_recipe(mechanics_world):
    """Los rechazos dejan inventario y progreso idénticos."""
    world = mechanics_world
    before = await world.redis.hgetall(RedisKeys.player_skills(1))
    for recipe, quantity in [
        ("herreria:15", 1),
        ("inventada", 1),
        ("carpinteria:480", 0),
        ("carpinteria:480", 101),
    ]:
        result = await craft(world.player, world.inventory, world.terrain, 1, recipe, quantity)
        assert result["applied"] is False
    assert await world.redis.hgetall(RedisKeys.player_skills(1)) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("success", [True, False])
async def test_meditation_uses_persistent_deadline_and_trains_valid_attempt(
    mechanics_world, success
):
    """Un tick vencido se aplica una vez, incluso si dos ejecutores lo reciben."""
    world = mechanics_world
    key = RedisKeys.player_user_stats(1)
    await world.redis.hset(key, mapping={"meditating": "1", "meditation_due": "10"})
    with patch("src.services.meditation.random.random", return_value=0.0 if success else 0.99):
        results = await asyncio.gather(
            *(meditate_tick(world.player, 1, 3, now=11) for _ in range(2))
        )
    assert sum(bool(r.get("applied")) for r in results) == 1
    assert await world.redis.hget(key, "min_mana") == ("55" if success else "50")
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:meditar") == (
        "50" if success else "20"
    )
    assert await world.redis.hget(key, "meditation_due") == "14"


@pytest.mark.asyncio
async def test_full_mana_stops_meditation_without_training(mechanics_world):
    """Tener maná completo no permite farmear Meditar."""
    world = mechanics_world
    await world.redis.hset(
        RedisKeys.player_user_stats(1), mapping={"meditating": "1", "min_mana": "100"}
    )
    result = await meditate_tick(world.player, 1, 3, now=11)
    assert result["stopped"] is True
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:meditar") == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("skill", "weapon", "ranged"),
    [("wrestling", 0, False), ("armas", 15, False), ("proyectiles", 665, True)],
)
@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("individual", [True, False])
async def test_physical_attack_uses_real_weapon_and_consumes_ammo_once(
    mechanics_world, skill, weapon, ranged, success, individual
):
    """Las tres habilidades físicas cambian el ataque y entrenan éxito o fallo válido."""
    world = mechanics_world
    if weapon:
        await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", f"{weapon}:1")
        await world.redis.hset(RedisKeys.player_equipment(1), "weapon", "1")
    if ranged:
        await world.redis.hset(RedisKeys.player_inventory(1), "slot_2", "480:3")
    iid = ""
    if individual:
        await migrate_items(world.redis.redis)
        if weapon:
            iid = InventorySlot.parse(
                await world.redis.hget(RedisKeys.player_inventory(1), "slot_1")
            ).instance_ids[0]
    with patch(
        "src.services.combat.physical_plan.random.random",
        side_effect=[0.0 if success else 0.99, 0.99, 0.99, 0.5, 0.99],
    ):
        plan = PhysicalPlan(
            PhysicalRequest(1, target_npc="animal", ranged=ranged), world.catalog, 30, 20
        )
    identity = operation_id()
    first = await commit_physical(world.redis.redis, plan, identity)
    saved = await world.redis.hgetall(RedisKeys.player_user_stats(1))
    assert first["applied"] is True
    assert first["dodged"] is not success
    assert first == await commit_physical(world.redis.redis, plan, identity)
    assert await world.redis.hgetall(RedisKeys.player_user_stats(1)) == saved
    assert saved["min_sta"] == "98"
    assert await world.redis.hget(RedisKeys.player_skills(1), f"xp:{skill}") == (
        "50" if success else "20"
    )
    if iid:
        assert await world.redis.hget(PREFIX + iid, "uses_spent") == "1"
    if ranged:
        assert await world.inventory.get_slot(1, 2) == (480, 2)


@pytest.mark.asyncio
async def test_backstab_trains_assassin_from_zero_and_adds_damage(mechanics_world):
    """El asesino puede comenzar desde cero con daga; se respeta la curva clásica."""
    world = mechanics_world
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "15:1")
    await world.redis.hset(RedisKeys.player_equipment(1), "weapon", "1")
    with patch(
        "src.services.combat.physical_plan.random.random", side_effect=[0.0, 0.99, 0.0, 0.5, 0.99]
    ):
        plan = PhysicalPlan(PhysicalRequest(1, target_npc="animal"), world.catalog, 30, 20)
    result = await commit_physical(world.redis.redis, plan, operation_id())
    assert result["backstab"] is True
    assert result["damage"] == 36
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:apunalar") == "50"


@pytest.mark.asyncio
async def test_own_critical_is_independent_of_the_weapon_damage_roll(mechanics_world):
    """Se conserva el crítico propio de 2x con una tirada independiente del daño."""
    world = mechanics_world
    results = []
    for critical_roll in (0.99, 0.0):
        with patch(
            "src.services.combat.physical_plan.random.random",
            side_effect=[0.0, 0.99, 0.99, 0.5, critical_roll],
        ):
            plan = PhysicalPlan(PhysicalRequest(1, target_npc="animal"), world.catalog, 30, 20)
        results.append(await commit_physical(world.redis.redis, plan, operation_id()))
    assert results[0]["critical"] is False
    assert results[1]["critical"] is True
    assert results[1]["damage"] == 2 * results[0]["damage"]


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["robustez", "agilidad"])
async def test_own_manual_extensions_have_effect_and_do_not_train(mechanics_world, extension):
    """Comparar 0/100 prueba su efecto sin convertirlas en atributos ni XP natural."""
    world = mechanics_world
    results = []
    for level in (0, 100):
        await world.redis.hset(RedisKeys.player_skills(1), f"level:{extension}", str(level))
        await world.redis.hset(RedisKeys.npc_instance("animal"), "last_attack_time", "0")
        with patch(
            "src.services.combat.physical_plan.random.random",
            side_effect=[0.20 if extension == "agilidad" else 0.99, 0.99],
        ):
            results.append(
                await defend_npc(world.redis.redis, 1, "animal", world.catalog, 100, operation_id())
            )
    assert results[0]["damage"] > results[1]["damage"]
    assert await world.redis.hget(RedisKeys.player_skills(1), f"xp:{extension}") == "0"
    assert await world.redis.hget(RedisKeys.player_stats(1), "agility") == "20"


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["evade", "shield", "hit"])
async def test_defense_trains_tactics_and_only_equipped_shield(mechanics_world, outcome):
    """Defensa requiere escudo; evasión y mitigación propias tienen efectos distintos."""
    world = mechanics_world
    await world.redis.hset(
        RedisKeys.player_skills(1),
        mapping={
            "level:tacticas": "50",
            "level:defensa": "50",
            "level:agilidad": "100",
            "level:robustez": "100",
        },
    )
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "404:1")
    await world.redis.hset(RedisKeys.player_equipment(1), "shield", "1")
    rolls = [0.0 if outcome == "evade" else 0.99, 0.0 if outcome == "shield" else 0.99]
    with patch("src.services.combat.physical_plan.random.random", side_effect=rolls):
        result = await defend_npc(
            world.redis.redis, 1, "animal", world.catalog, 100, operation_id()
        )
    assert result["applied"] is True
    assert result["damage"] == (81 if outcome == "hit" else 0)
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:tacticas") == (
        "50" if outcome == "evade" else "20"
    )
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:defensa") == (
        "0" if outcome == "evade" else "50" if outcome == "shield" else "20"
    )


@pytest.mark.asyncio
async def test_pvp_safe_distance_and_ammo_rejections_have_no_training(mechanics_world):
    """Ningún rechazo de alcance, seguro o munición consume stamina ni XP."""
    world = mechanics_world
    await world.redis.hset(RedisKeys.player_user_stats(2), "safe_mode", "1")
    for request in [
        PhysicalRequest(1, target_player=2),
        PhysicalRequest(1, target_npc="animal", ranged=True),
    ]:
        plan = PhysicalPlan(request, world.catalog, 30, 20)
        result = await commit_physical(world.redis.redis, plan, operation_id())
        assert result["applied"] is False
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "min_sta") == "100"
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:wrestling") == "0"


@pytest.mark.asyncio
async def test_hide_persists_duration_and_toggle_cannot_duplicate_training(mechanics_world):
    """El segundo uso revela; no concede otra tanda de experiencia."""
    world = mechanics_world
    with patch("src.services.personal_skills.random.random", return_value=0.0):
        first = await hide(world.player, 1, operation_id())
        assert first["successful"] is True
        assert float(await world.redis.hget(RedisKeys.player_user_stats(1), "hidden_until")) > 0
        await hide(world.player, 1, operation_id())
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "hidden_until") == "0"
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:ocultarse") == "50"


@pytest.mark.asyncio
@pytest.mark.parametrize("thief", [True, False])
async def test_steal_conserves_total_gold_or_items_and_replay(mechanics_world, thief):
    """Toda clase roba oro; Ladrón puede tomar un objeto no equipado."""
    world = mechanics_world
    await world.redis.hset(RedisKeys.player_user_stats(1), "class_id", "5" if thief else "3")
    await world.redis.hset(RedisKeys.player_inventory(2), "slot_1", "58:3")
    identity = operation_id()
    with patch("src.services.personal_skills.random.random", return_value=0.0):
        first = await steal(world.player, world.inventory, world.catalog, 1, 2, identity)
        second = await steal(world.player, world.inventory, world.catalog, 1, 2, identity)
    assert first == second
    assert first["successful"] is True
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:robar") == "50"
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "min_sta") == "85"
    if thief:
        assert await world.inventory.get_slot(1, 1) == (58, 1)
        assert await world.inventory.get_slot(2, 1) == (58, 2)
    else:
        balances = [
            int(await world.redis.hget(RedisKeys.player_user_stats(u), "gold")) for u in (1, 2)
        ]
        assert sum(balances) == 2000
        assert balances[0] > 1000


@pytest.mark.asyncio
async def test_survival_fire_consumes_fuel_once_and_survives_repository_recreation(mechanics_world):
    """La fogata queda en Redis con TTL y no se duplica al reenviar la operación."""
    world = mechanics_world
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "58:6")
    identity = operation_id()
    with patch("src.services.personal_skills.random.random", return_value=0.0):
        first = await survival(world.player, world.inventory, world.terrain, 1, 2, 49, 50, identity)
        second = await survival(
            world.player, world.inventory, world.terrain, 1, 2, 49, 50, identity
        )
    assert first == second
    assert first["fire"] is True
    assert await world.inventory.get_slot(1, 1) == (58, 3)
    assert int(await world.redis.redis.ttl("world:campfire:2:49:50")) > 0
    assert await world.redis.smembers("world:campfires:2") == {"world:campfire:2:49:50"}
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:supervivencia") == "50"


@pytest.mark.asyncio
async def test_competing_fires_and_lost_ack_keep_one_fuel_charge(mechanics_world):
    """Dos jugadores compiten por la casilla; sólo uno paga y su reintento es idéntico."""
    world = mechanics_world
    for user in (1, 2):
        await world.redis.hset(RedisKeys.player_inventory(user), "slot_1", "58:6")
    identities = [operation_id(), operation_id()]
    with patch("src.services.personal_skills.random.random", return_value=0.0):
        results = await asyncio.gather(
            *(
                survival(world.player, world.inventory, world.terrain, user, 2, 49, 50, identity)
                for user, identity in zip((1, 2), identities, strict=True)
            )
        )
        winner = next(index for index, result in enumerate(results) if result.get("fire"))
        repeated = await survival(
            world.player, world.inventory, world.terrain, winner + 1, 2, 49, 50, identities[winner]
        )
    assert sum(bool(result.get("fire")) for result in results) == 1
    assert repeated == results[winner]
    assert sum([(await world.inventory.get_slot(user, 1))[1] for user in (1, 2)]) == 9
    assert await world.redis.smembers("world:campfires:2") == {"world:campfire:2:49:50"}


@pytest.mark.asyncio
async def test_taming_uses_charisma_and_permanent_pet_survives_world_cleanup(mechanics_world):
    """Domar exige umbral, crea propiedad permanente y la limpieza preserva la criatura."""
    world = mechanics_world
    await world.redis.hset(RedisKeys.player_skills(1), "level:domar", "20")
    with patch("src.services.personal_skills.random.random", return_value=0.0):
        result = await tame(world.player, 1, "animal", [], operation_id())
    assert result["successful"] is True
    pet = await world.npcs.get_npc("animal")
    assert pet.is_tamed is True
    assert pet.summoned_by_user_id == 1
    assert pet.summoned_until == 0
    await world.npcs.clear_all_npcs(preserve_tamed=True)
    assert (await world.npcs.get_npc("animal")).is_tamed is True
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:domar") == "50"
    rejected = await tame(world.player, 2, "animal", [], operation_id())
    assert rejected["applied"] is False
    await world.redis.sadd(RedisKeys.npc_map_index(99), "animal", "missing")
    await world.redis.redis.delete(RedisKeys.npc_map_index(2), "player:1:pets")
    await world.npcs.clear_all_npcs(preserve_tamed=True)
    assert await world.redis.redis.smembers(RedisKeys.npc_map_index(2)) == {"animal"}
    assert not await world.redis.redis.smembers(RedisKeys.npc_map_index(99))
    assert "animal" in await world.redis.redis.smembers("player:1:pets")


@pytest.mark.asyncio
@pytest.mark.parametrize(("player_class", "required"), [(12, 35), (11, 70), (3, 70)])
async def test_navigation_manual_skill_enforces_class_and_boat_requirement(
    mechanics_world, player_class, required
):
    """El barco necesita conocimiento y costa; usarlo no entrena Navegación."""
    world = mechanics_world
    world.terrain.has_water = lambda _map, x, _y: x > 50
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "474:1")
    await world.redis.hset(RedisKeys.player_user_stats(1), "class_id", str(player_class))
    await world.redis.hset(RedisKeys.player_skills(1), "level:navegacion", str(required - 1))
    first = await navigate(
        world.player, world.inventory, world.catalog, world.terrain, 1, 1, operation_id()
    )
    assert first["applied"] is False
    assert first["required"] == required
    await world.redis.hset(RedisKeys.player_skills(1), "level:navegacion", str(required))
    second = await navigate(
        world.player, world.inventory, world.catalog, world.terrain, 1, 1, operation_id()
    )
    assert second["sailing"] is True
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:navegacion") == "0"


@pytest.mark.asyncio
async def test_commerce_skill_changes_quote_and_trains_confirmed_purchase(mechanics_world):
    """El regateo usa la misma cotización para cobrar y no duplica XP ni objetos."""
    world = mechanics_world
    await world.redis.hset(RedisKeys.merchant_inventory(1), "slot_1", "15:10")
    await world.redis.hset(RedisKeys.player_skills(1), "level:comerciar", "50")
    service = CommerceService(
        world.inventory, MerchantRepository(world.redis), ITEMS_CATALOG, world.player
    )
    identity = operation_id()
    with patch("src.services.commerce_service.require_durable", new=AsyncMock()):
        first = await service.buy_item(1, 1, 1, 2, operation_id=identity)
        second = await service.buy_item(1, 1, 1, 2, operation_id=identity)
    assert first == second
    assert first[0] is True
    assert int(
        await world.redis.hget(RedisKeys.player_user_stats(1), "gold")
    ) == 1000 - 2 * commerce_price(ITEMS_CATALOG[15].value, 50, "buy")
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:comerciar") == "50"
    assert await world.inventory.get_slot(1, 1) == (15, 2)
    assert commerce_price(ITEMS_CATALOG[15].value, 100, "buy") >= commerce_price(
        ITEMS_CATALOG[15].value, 100, "sell"
    )


@pytest.mark.asyncio
async def test_leadership_manual_gates_party_and_clan_using_dataset_rules(mechanics_world):
    """Liderazgo sólo se asigna: sus requisitos afectan nuevas creaciones y no dan XP."""
    world = mechanics_world
    party = PartyService(PartyRepository(world.redis), world.player, AsyncMock())
    clan = ClanService(ClanRepository(world.redis), world.player, AsyncMock())
    assert (await party.can_create_party(1))[0] is False
    assert (await clan.can_create_clan(1, "Ejemplo"))[0] is False
    await world.redis.hset(RedisKeys.player_skills(1), "level:liderazgo", "5")
    assert (await party.can_create_party(1))[0] is True
    rules = json.loads(await world.redis.get(SKILL_RULES_KEY))
    rules["leadership_party_score"] = 120
    await world.redis.set(SKILL_RULES_KEY, json.dumps(rules))
    assert (await party.can_create_party(1))[0] is False
    await world.redis.hset(RedisKeys.player_skills(1), "level:liderazgo", "90")
    assert (await clan.can_create_clan(1, "Ejemplo"))[0] is True
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:liderazgo") == "0"
