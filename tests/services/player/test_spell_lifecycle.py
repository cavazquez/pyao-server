"""Magia real sobre Redis: autoridad, costes y efectos sin mocks de saldos."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError

from src.effects.effect_lifecycle import LifecycleEffect
from src.game.map_manager import MapManager
from src.messaging.senders.message_status_effects_sender import StatusEffectsMessageSender
from src.models.item_catalog import ItemCatalog
from src.models.npc import NPC
from src.models.npc_catalog import NPCCatalog
from src.models.spell_catalog import SpellCatalog
from src.repositories.account_repository import AccountRepository
from src.repositories.ground_items_repository import GroundItemsRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.services.combat.pvp_policy import PvpPolicy
from src.services.combat.spell_plan import CastRequest, SpellPlan, commit_spell
from src.services.npc.npc_service import NPCService
from src.services.npc.summon_service import SummonService
from src.services.player.lifecycle import apply_player_damage, resurrect, settle_death
from src.services.player.player_death_service import PlayerDeathService
from src.services.player.spell_service import SpellService
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def world(redis_client, monkeypatch):
    """Dos personajes con libro, mapa e inventarios sobre Redis descartable.

    Yields:
        Mundo sintético que se cierra al terminar cada escenario.
    """
    monkeypatch.setattr("src.services.combat.spell_plan.require_durable", AsyncMock())
    monkeypatch.setattr("src.services.player.lifecycle.require_durable", AsyncMock())
    player, npcs = PlayerRepository(redis_client), NPCRepository(redis_client)
    maps = MapManager(GroundItemsRepository(redis_client))
    senders = {1: AsyncMock(), 2: AsyncMock()}
    for user in (1, 2):
        await redis_client.hset(
            RedisKeys.account_data(f"usr{user}"),
            mapping={
                "user_id": str(user),
                "username": f"usr{user}",
                "char_race": "1",
                "char_head": "1",
                "char_class": "1",
            },
        )
        await redis_client.hset(
            RedisKeys.player_user_stats(user),
            mapping={
                "min_hp": "100",
                "max_hp": "100",
                "min_mana": "5000",
                "max_mana": "5000",
                "min_sta": "5000",
                "max_sta": "5000",
                "gold": "1000",
                "experience": "1000",
                "safe_mode": "0",
                "life_id": "0",
                "death_state": "alive",
            },
        )
        await player.set_position(user, 49 + user, 50, 2, 3)
        await redis_client.hset(RedisKeys.player_skills(user), mapping={"level:magia": "100"})
        await redis_client.hset(
            RedisKeys.player_stats(user),
            mapping={"intelligence": "20", "strength": "10", "agility": "10"},
        )
        await redis_client.hset(
            RedisKeys.player_spellbook(user),
            mapping={str(slot): str(slot) for slot in range(1, 36)},
        )
        await redis_client.hset(
            RedisKeys.player_hunger_thirst(user),
            mapping={
                "max_water": "100",
                "min_water": "100",
                "max_hunger": "100",
                "min_hunger": "100",
            },
        )
        maps.add_player(2, user, senders[user], f"usr{user}")
    catalog, broadcast = SpellCatalog(), AsyncMock()
    death = PlayerDeathService(
        maps,
        player,
        broadcast,
        InventoryRepository(redis_client),
        ItemCatalog(),
        AccountRepository(redis_client),
    )
    NPCService.reset_instance()
    npc_service = NPCService(npcs, NPCCatalog(), maps, broadcast)
    service = SpellService(
        catalog,
        player,
        npcs,
        maps,
        account_repo=AccountRepository(redis_client),
        broadcast_service=broadcast,
        npc_service=npc_service,
        summon_service=SummonService(npcs, player),
        player_death_service=death,
        item_catalog=ItemCatalog(),
    )
    yield SimpleNamespace(
        client=redis_client,
        player=player,
        npcs=npcs,
        maps=maps,
        senders=senders,
        service=service,
        death=death,
        catalog=catalog,
    )
    await death.close()
    NPCService.reset_instance()


async def cast(world, spell=2, x=51, y=50, **kwargs: object):
    """Invoca el servicio real con slot y coordenadas explícitos."""
    return await world.service.cast_spell(1, spell, x, y, world.senders[1], slot=spell, **kwargs)


@pytest.mark.asyncio
async def test_cost_and_damage_once_and_replay(world):
    """Repetir una intención no vuelve a cobrar ni a dañar."""
    identity = operation_id()
    assert await cast(world, identity=identity)
    after = await world.client.hgetall(RedisKeys.player_user_stats(1))
    target = await world.client.hgetall(RedisKeys.player_user_stats(2))
    assert after["min_mana"] == "4990"
    assert after["min_sta"] == "4999"
    assert 94 <= int(target["min_hp"]) <= 98
    assert await cast(world, identity=identity)
    assert await world.client.hgetall(RedisKeys.player_user_stats(1)) == after
    assert await world.client.hgetall(RedisKeys.player_user_stats(2)) == target


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "empty_slot",
        "mana",
        "stamina",
        "range",
        "missing",
        "self_damage",
        "safe_source",
        "safe_target",
        "safe_map",
        "dead_caster",
        "dead_target",
        "skill",
        "dumb",
        "staff",
        "target_map",
    ],
)
async def test_rejection_has_no_cost_or_effect(world, case):
    """Ningún rechazo de dominio cambia maná, stamina o HP."""
    x, y, spell = 51, 50, 2
    if case == "empty_slot":
        await world.client.hdel(RedisKeys.player_spellbook(1), "2")
    elif case in {"mana", "stamina", "dead_caster", "safe_source", "dumb"}:
        field, value = {
            "mana": ("min_mana", "0"),
            "stamina": ("min_sta", "0"),
            "dead_caster": ("min_hp", "0"),
            "safe_source": ("safe_mode", "1"),
            "dumb": ("dumb_until", str(time.time() + 100)),
        }[case]
        await world.client.hset(RedisKeys.player_user_stats(1), field, value)
    elif case in {"dead_target", "safe_target"}:
        await world.client.hset(
            RedisKeys.player_user_stats(2),
            "min_hp" if case == "dead_target" else "safe_mode",
            "0" if case == "dead_target" else "1",
        )
    elif case == "skill":
        await world.client.hset(RedisKeys.player_skills(1), "level:magia", "0")
    elif case == "staff":
        spell = 11
        await world.client.hset(
            RedisKeys.player_user_stats(2), mapping={"min_hp": "0", "death_state": "complete"}
        )
    elif case == "safe_map":
        for user in (1, 2):
            world.maps.remove_player(2, user)
            world.maps.add_player(1, user, world.senders[user], f"usr{user}")
            await world.player.set_position(user, 49 + user, 50, 1, 3)
    elif case == "target_map":
        await world.player.set_position(2, 51, 50, 3, 3)
    elif case == "range":
        x = 70
    elif case == "missing":
        x = 52
    elif case == "self_damage":
        x = 50
    before = {
        user: await world.client.hgetall(RedisKeys.player_user_stats(user)) for user in (1, 2)
    }
    assert not await cast(world, spell, x, y)
    assert {
        user: await world.client.hgetall(RedisKeys.player_user_stats(user)) for user in (1, 2)
    } == before


@pytest.mark.asyncio
async def test_atomic_snapshot_revalidates_target_state(world):
    """Una autorización previa no sirve si cambia el seguro antes del commit."""
    plan = SpellPlan(CastRequest(1, 2, 51, 50, 2, 2), world.catalog.get_spell_data(2), PvpPolicy())
    await world.client.hset(RedisKeys.player_user_stats(2), "safe_mode", "1")
    assert not (await commit_spell(world.client.redis, operation_id(), plan))["applied"]
    assert (await world.player.get_mana(1))[0] == 5000


@pytest.mark.asyncio
async def test_parallel_casts_cannot_overspend(world):
    """Dos casts distintos compiten por una sola dosis completa de recursos."""
    await world.client.hset(
        RedisKeys.player_user_stats(1), mapping={"min_mana": "10", "min_sta": "1"}
    )
    assert sum(await asyncio.gather(cast(world), cast(world))) == 1
    assert (await world.player.get_mana(1))[0] == 0
    assert (await world.player.get_stamina(1))[0] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("spell", "field"),
    [
        (4, "poisoned_until"),
        (9, "immobilized_until"),
        (24, "immobilized_until"),
        (31, "dumb_until"),
        (19, "agility_modifier_until"),
        (21, "strength_modifier_until"),
    ],
)
async def test_status_and_debuffs_are_confirmed_with_cost(world, spell, field):
    """Daño de estado y debuffs consultan PvP y persisten con el coste."""
    assert await cast(world, spell)
    key = RedisKeys.player_stats(2) if "modifier" in field else RedisKeys.player_user_stats(2)
    assert float(await world.client.hget(key, field)) > time.time()


@pytest.mark.asyncio
async def test_healing_self_and_cure_are_allowed_in_safe_mode(world):
    """La política de PvP permite curar al propio personaje."""
    await world.client.hset(
        RedisKeys.player_user_stats(1),
        mapping={"min_hp": "50", "safe_mode": "1", "poisoned_until": str(time.time() + 30)},
    )
    assert await cast(world, 3, 50, 50)
    assert await world.player.get_current_hp(1) > 50
    assert await cast(world, 1, 50, 50)
    assert await world.player.get_poisoned_until(1) == 0


@pytest.mark.asyncio
async def test_two_lethal_sources_settle_one_life_and_revive_next_life(world):
    """Combate y veneno no duplican pérdidas; revivir permite otra muerte válida."""
    await world.client.hset(
        RedisKeys.player_inventory(2), mapping={"slot_1": "1:5", "slot_30": "199:1"}
    )
    results = await asyncio.gather(
        *(apply_player_damage(world.client.redis, 2, 100, operation_id()) for _ in range(2))
    )
    assert sum(result["player_died"] for result in results) == 1
    settled = await asyncio.gather(
        *(settle_death(world.client.redis, 2, 0, 2, 51, 50) for _ in range(2))
    )
    assert sum(result["applied"] for result in settled) == 1
    stats = await world.client.hgetall(RedisKeys.player_user_stats(2))
    assert stats["experience"] == "950"
    assert stats["gold"] == "900"
    assert stats["death_state"] == "complete"
    revivals = await asyncio.gather(
        *(resurrect(world.client.redis, 2, operation_id()) for _ in range(2))
    )
    assert sum(result["applied"] for result in revivals) == 1
    assert await world.player.get_current_hp(2) == 50
    result = await apply_player_damage(world.client.redis, 2, 100, operation_id())
    assert result["life_id"] == 1
    assert result["player_died"]
    assert not (await settle_death(world.client.redis, 2, 0, 2, 51, 50))["applied"]
    assert (await settle_death(world.client.redis, 2, 1, 2, 51, 50))["applied"]
    assert await world.client.hget(RedisKeys.player_user_stats(2), "experience") == "903"


@pytest.mark.asyncio
async def test_revive_spell_uses_common_lifecycle_and_no_charge_for_live_target(world):
    """Hechizo y sacerdote comparten la restauración y no cobran por un vivo."""
    world.catalog.spells[11] = dict(world.catalog.spells[11], need_staff=False)
    await apply_player_damage(world.client.redis, 2, 100, operation_id())
    await world.death.handle_player_death(2, "prueba")
    assert await cast(world, 11)
    assert await world.player.get_current_hp(2) == 50
    after = await world.player.get_mana(1)
    assert not await cast(world, 11)
    assert await world.player.get_mana(1) == after


@pytest.mark.asyncio
async def test_summoning_and_warp_confirm_pet_and_cost_together(world):
    """El catálogo propio invoca dos mascotas y el replay conserva ambas y el coste."""
    identity = operation_id()
    assert await cast(world, 16, 52, 50, identity=identity), world.senders[
        1
    ].send_console_msg.await_args_list
    pets = await world.service.summon_service.get_player_pets(1)
    assert len(pets) == 2
    mana = await world.player.get_mana(1)
    assert await cast(world, 16, 52, 50, identity=identity)
    assert await world.player.get_mana(1) == mana
    assert len(await world.service.summon_service.get_player_pets(1)) == 2
    await world.client.hset(RedisKeys.player_spellbook(1), "1", "46")
    assert await world.service.cast_spell(1, 46, 50, 50, world.senders[1], slot=1)
    pet = await world.npcs.get_npc(pets[0])
    assert (pet.map_id, pet.x, pet.y) == (2, 50, 50)


@pytest.mark.asyncio
@pytest.mark.parametrize(("spell", "initial_hp"), [(2, 100), (2, 1), (3, 50), (4, 100), (9, 100)])
async def test_real_npc_effects_and_intelligence(world, spell, initial_hp):
    """Daño, muerte, curación, veneno y parálisis se confirman junto al coste."""
    await world.player.set_position(2, 70, 70, 2, 3)
    npc = await world.npcs.create_npc_instance(
        npc_id=1,
        char_index=10001,
        map_id=2,
        x=51,
        y=50,
        heading=3,
        name="Orco",
        description="Sintético",
        body_id=1,
        head_id=0,
        hp=initial_hp,
        max_hp=100,
        level=1,
        is_hostile=True,
        is_attackable=True,
        respawn_time=0,
        respawn_time_max=0,
        gold_min=0,
        gold_max=0,
    )
    world.maps.add_npc(2, npc)
    assert await cast(world, spell)
    saved = await world.npcs.get_npc(npc.instance_id)
    if spell == 2:
        assert saved.hp < initial_hp
        assert saved.hp == npc.hp
    elif spell == 3:
        assert saved.hp > initial_hp
    elif spell == 4:
        assert saved.poisoned_until > time.time()
    elif spell == 9:
        assert saved.paralyzed_until > time.time()
    assert (await world.player.get_mana(1))[0] == 5000 - world.catalog.spells[spell]["mana_cost"]


@pytest.mark.asyncio
async def test_unknown_spell_and_visual_effects(world):
    """Rechazar un ID inexistente no cobra; el FX se publica tras confirmar el cast."""
    assert not await cast(world, 254)
    assert (await world.player.get_mana(1))[0] == 5000
    assert await cast(world)
    world.senders[1].send_create_fx_at_position.assert_awaited_once()
    world.catalog.spells[2] = dict(world.catalog.spells[2], fx_grh=0)
    world.senders[1].send_create_fx_at_position.reset_mock()
    assert await cast(world)
    world.senders[1].send_create_fx_at_position.assert_not_awaited()


@pytest.mark.asyncio
async def test_morph_invisibility_and_hunger(world):
    """La confirmación conserva los efectos propios y sus flags en el jugador."""
    await world.client.hset(RedisKeys.player_spellbook(1), mapping={"1": "42", "2": "14"})
    assert await world.service.cast_spell(1, 42, 51, 50, world.senders[1], slot=1)
    assert (await world.player.get_morphed_appearance(1))["morphed_body"] == 1
    assert await world.service.cast_spell(1, 14, 50, 50, world.senders[1], slot=2)
    assert await world.player.get_invisible_until(1) > time.time()
    assert await cast(world, 12)
    assert (await world.player.get_hunger_thirst(2))["min_hunger"] == 50


@pytest.mark.asyncio
async def test_staff_comes_from_item_properties_and_priest_revalidates_range(world):
    """Un báculo es válido aunque su nombre no diga bastón; el sacerdote exige cercanía."""
    await world.client.hset(RedisKeys.player_inventory(1), mapping={"slot_30": "660:1"})
    await world.client.hset(RedisKeys.player_equipment(1), mapping={"weapon": "30"})
    await apply_player_damage(world.client.redis, 2, 100, operation_id())
    await world.death.handle_player_death(2, "prueba")
    assert await cast(world, 11)
    await apply_player_damage(world.client.redis, 2, 100, operation_id())
    await world.death.handle_player_death(2, "prueba")
    priest = NPC(
        npc_id=119,
        char_index=10001,
        instance_id="synthetic-priest",
        is_hostile=False,
        is_attackable=False,
        map_id=2,
        x=52,
        y=50,
        heading=3,
        name="Sacerdote",
        description="",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
    )
    key = RedisKeys.npc_instance(priest.instance_id)
    await world.client.hset(
        key, mapping={"npc_id": "119", "map_id": "2", "x": "52", "y": "50", "hp": "100"}
    )
    await world.player.set_position(2, 70, 70, 2, 3)
    assert not (await resurrect(world.client.redis, 2, operation_id(), priest=priest))["applied"]
    await world.player.set_position(2, 51, 50, 2, 3)
    assert (await resurrect(world.client.redis, 2, operation_id(), priest=priest))["applied"]


@pytest.mark.asyncio
async def test_pending_death_does_not_block_tick_and_has_an_owner(world, monkeypatch):
    """Un AOF lento no retiene el tick y close espera la liquidación propia."""
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked(*_args: object, **_kwargs: object):
        entered.set()
        await release.wait()

    monkeypatch.setattr(world.death, "handle_player_death", blocked)
    await apply_player_damage(world.client.redis, 2, 100, operation_id())
    effect = LifecycleEffect(world.death)
    await asyncio.wait_for(effect.apply(2, world.player, world.senders[2]), 0.2)
    await asyncio.wait_for(entered.wait(), 0.2)
    await effect.apply(2, world.player, world.senders[2])
    assert len(world.death._jobs) == 1
    release.set()
    await world.death.close()
    assert not world.death._jobs


@pytest.mark.asyncio
async def test_lost_ack_internal_retry_has_one_cost_and_effect(world, monkeypatch):
    """El recibo resuelve un ACK perdido tras EXEC sin ejecutar el efecto otra vez."""
    pipeline_type = type(world.client.redis.pipeline())
    original = pipeline_type.execute
    lost = False

    async def execute(self, *args: object, **kwargs: object):
        nonlocal lost
        result = await original(self, *args, **kwargs)
        if not lost:
            lost = True
            message = "synthetic lost EXEC ACK"
            raise RedisConnectionError(message)
        return result

    monkeypatch.setattr(pipeline_type, "execute", execute)
    assert await cast(world)
    assert (await world.player.get_mana(1))[0] == 4990
    assert (await world.player.get_stamina(1))[0] == 4999
    assert 94 <= await world.player.get_current_hp(2) <= 98


@pytest.mark.asyncio
async def test_stale_poison_tick_cannot_damage_revived_life_or_clear_new_poison(world):
    """Un tick que leyó otra vida no afecta a un resucitado sin veneno."""
    await apply_player_damage(world.client.redis, 2, 100, operation_id())
    await world.death.handle_player_death(2, "prueba")
    assert (await resurrect(world.client.redis, 2, operation_id()))["applied"]
    result = await apply_player_damage(
        world.client.redis, 2, 5, operation_id(), require_poison=True
    )
    assert not result["applied"]
    assert await world.player.get_current_hp(2) == 50
    old_until = time.time() + 10
    new_until = old_until + 1
    await world.player.update_poisoned_until(2, new_until)
    await world.player.clear_poisoned_until_if(2, old_until)
    assert await world.player.get_poisoned_until(2) == new_until
    await world.player.clear_poisoned_until_if(2, new_until)
    assert await world.player.get_poisoned_until(2) == 0


@pytest.mark.asyncio
async def test_status_toggles_are_once_and_expiry_restores_controls(world):
    """Reintentos, expiry y resurrección no invierten un estado ya sincronizado."""
    connection = AsyncMock()
    statuses = StatusEffectsMessageSender(connection)
    until = str(time.time() + 30)
    key = RedisKeys.player_user_stats(2)
    await world.client.hset(
        key, mapping={"immobilized_until": until, "blinded_until": until, "dumb_until": until}
    )
    await statuses.sync_status(2, world.player)
    await statuses.sync_status(2, world.player)
    packets = [call.args[0] for call in connection.send.await_args_list]
    assert packets == [bytes([82]), bytes([56]), bytes([57])]
    await world.client.hset(
        key, mapping={"immobilized_until": "1", "blinded_until": "1", "dumb_until": "1"}
    )
    await statuses.sync_status(2, world.player)
    await statuses.sync_status(2, world.player)
    packets = [call.args[0] for call in connection.send.await_args_list]
    assert packets == [bytes([82]), bytes([56]), bytes([57]), bytes([82]), bytes([69]), bytes([70])]
