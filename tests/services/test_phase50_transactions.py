"""Concurrencia y autoridad de misiones, clanes, magia y efectos nuevos."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.models.clan import Clan, ClanMember, ClanRank
from src.models.npc import NPC
from src.models.party import Party
from src.models.potion_duration import normalize_potion_duration
from src.models.spell_extensions import validate_extensions
from src.security.chat_mutes import chat_rejection, moderate_chat
from src.services.combat.area_spell import AreaSpellPlan
from src.services.combat.barriers import absorb_damage
from src.services.combat.periodic import tick_periodic
from src.services.combat.pvp_policy import PvpPolicy
from src.services.combat.spell_plan import CastRequest, SpellPlan, commit_spell
from src.services.expansion.pages import bounded_pages
from src.services.personal_skills import tame
from src.services.player.lifecycle import apply_player_damage
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from tests.services.test_world_state import world

__all__ = ["world"]


def test_unicode_pages_obey_serialized_byte_limits():
    """La longitud visible del texto no sustituye su tamaño en el frame JSON ASCII."""
    rows = [{"text": "é" * 120, "id": index} for index in range(10)]
    pages = bounded_pages(rows, 4, 2000)
    assert len(pages) > 1
    assert [row for page in pages for row in page] == rows
    for page in pages:
        assert len(json.dumps(page, ensure_ascii=True, separators=(",", ":"))) <= 2000


@pytest.mark.asyncio
async def test_finder_paginates_long_ads_without_oversized_frames(world):
    """Todos los anuncios siguen consultables aunque el texto use acentos."""
    state, deps, _ = world
    for user in (1, 2, 3):
        await deps.party_repo.save_party(Party(user, user, f"User{user}"))
        result = await state.expansion.finder.command(
            user,
            "publish",
            {
                "min_level": 1,
                "max_level": 100,
                "activity": "caza",
                "text": "é" * 120,
                "seconds": 600,
            },
            operation_id(),
        )
        assert result["applied"], result
    first = await state.expansion.finder.snapshot(1, {"page": 0})
    observed = []
    for page in range(first["pages"]):
        payload = await state.expansion.finder.snapshot(1, {"page": page})
        assert (
            len(json.dumps({"kind": "finder", "data": payload}, ensure_ascii=True).encode()) < 3500
        )
        observed.extend(row["id"] for row in payload["rows"])
    assert len(set(observed)) == len(observed) == 3


@pytest.mark.asyncio
async def test_enemy_dispel_cannot_bypass_safe_maps(world):
    """Disipar protecciones de otro jugador requiere la misma autorización PvP."""
    _, deps, _ = world
    await deps.redis_client.hset(
        RedisKeys.player_user_stats(1), mapping={"min_mana": 100, "min_sta": 100, "safe_mode": 0}
    )
    await deps.redis_client.hset(
        RedisKeys.player_user_stats(2),
        mapping={"safe_mode": 0, "barrier_capacity": 100, "barrier_until": time.time() + 30},
    )
    await deps.redis_client.hset(RedisKeys.player_spellbook(1), "1", "51")
    plan = SpellPlan(
        CastRequest(1, 51, 52, 50, 1, 2), {"mana_cost": 20, "dispels_magic": True}, PvpPolicy()
    )
    with patch("src.services.combat.spell_plan.require_durable", new=AsyncMock()):
        result = await commit_spell(deps.redis_client.redis, operation_id(), plan)
    assert not result["applied"]
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(2), "barrier_capacity") == "100"
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "min_mana") == "100"


@pytest.mark.asyncio
async def test_two_tamers_cannot_own_the_same_creature(world):
    """La propiedad y los cupos comparten WATCH con la tirada y el cooldown."""
    _, deps, _ = world
    await deps.player_repo.set_position(2, 52, 51, 1, 3)
    await deps.redis_client.hset(
        "npc:instance:wild",
        mapping={
            "npc_id": 500,
            "map_id": 1,
            "x": 51,
            "y": 51,
            "hp": 100,
            "domable": 400,
            "summoned_by_user_id": 0,
        },
    )
    for user in (1, 2):
        await deps.redis_client.hset(RedisKeys.player_user_stats(user), "class_id", 1)
        await deps.redis_client.hset(RedisKeys.player_stats(user), "charisma", 20)
        await deps.redis_client.hset(RedisKeys.player_skills(user), "level:domar", 100)
    with patch("src.services.personal_skills.random.random", return_value=0.0):
        results = await asyncio.gather(
            *(tame(deps.player_repo, user, "wild", [], operation_id()) for user in (1, 2))
        )
    assert sum(result.get("successful", False) for result in results) == 1, results
    owner = int(await deps.redis_client.hget("npc:instance:wild", "summoned_by_user_id"))
    assert owner in {1, 2}
    assert await deps.redis_client.redis.smembers(f"player:{owner}:pets") == {"wild"}
    assert not await deps.redis_client.redis.smembers(f"player:{3 - owner}:pets")
    assert not (await tame(deps.player_repo, owner, "wild", ["wild"], operation_id()))["applied"]


async def quest_giver(deps):
    """Instancia una entidad autorizada; no ejecuta ninguna acción del jugador."""
    npc = NPC(
        npc_id=2,
        char_index=12000,
        instance_id="quest-giver",
        map_id=1,
        x=51,
        y=50,
        heading=3,
        name="Misiones",
        description="",
        body_id=1,
        head_id=0,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=False,
        is_attackable=False,
    )
    deps.map_manager.add_npc(1, npc)
    await deps.redis_client.hset(
        RedisKeys.npc_instance(npc.instance_id),
        mapping={"npc_id": 2, "map_id": 1, "x": 51, "y": 50, "hp": 100},
    )
    return npc


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), 86401])
def test_attribute_duration_rejects_unbounded_values(duration):
    """Un dato inválido no puede crear buffs permanentes ni instantáneos."""
    with pytest.raises(ValueError, match="EffectDurationSeconds"):
        normalize_potion_duration({"TipoPocion": 1, "EffectDurationSeconds": duration})


def test_original_potion_ticks_are_forty_seconds():
    """El contador de AO es de 40 ms, no milisegundos."""
    assert (
        normalize_potion_duration({"TipoPocion": 1, "DuracionEfecto": 1000})[
            "EffectDurationSeconds"
        ]
        == 40
    )


@pytest.mark.parametrize(
    "rule",
    [
        {"components": [{"item": 9999, "quantity": 1}]},
        {"area": {"radius": 5, "max_targets": 16}},
        {"periodic": {"mode": "damage", "interval_seconds": 5, "duration_seconds": 1, "amount": 1}},
        {"barrier": {"capacity": 10001, "duration_seconds": 2, "damage_types": ["magic"]}},
    ],
)
def test_spell_rules_reject_invalid_refs_and_bounds(rule):
    """Ninguna extensión puede ampliar límites o inventar objetos por datos."""
    with pytest.raises(ValueError, match=r"components|radius|duration_seconds|capacity"):
        validate_extensions({"target": 1, **rule}, {406, 407})


@pytest.mark.asyncio
async def test_delivery_and_reward_are_exactly_once(world):
    """Dos peticiones paralelas no duplican entrega, oro, XP ni objetos."""
    state, deps, _ = world
    npc = await quest_giver(deps)
    quests = state.expansion.quests
    params = {"quest": "primeros-suministros", "npc": npc.char_index}
    await deps.redis_client.hset(RedisKeys.player_inventory(1), "slot_1", "58:5")
    assert (await quests.command(1, "accept", params, operation_id()))["applied"]
    deliveries = await asyncio.gather(
        *(quests.command(1, "deliver", params, operation_id()) for _ in range(2))
    )
    assert sum(row["applied"] for row in deliveries) == 1
    assert (await deps.inventory_repo.get_slot(1, 1)) is None
    claims = await asyncio.gather(
        *(quests.command(1, "claim", params, operation_id()) for _ in range(2))
    )
    assert sum(row["applied"] for row in claims) == 1
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "gold") == "1025"
    assert (
        sum(
            int(value.split(":")[1])
            for value in (await deps.inventory_repo.get_inventory(1)).values()
            if value.startswith("38:")
        )
        == 3
    )
    assert (
        json.loads(await deps.redis_client.hget("quests:1", "primeros-suministros"))["status"]
        == "claimed"
    )


@pytest.mark.asyncio
async def test_failed_reward_does_not_mark_claimed_or_pay_gold(world):
    """Un inventario lleno conserva intacto el premio para cobrarlo después."""
    state, deps, _ = world
    npc = await quest_giver(deps)
    await deps.redis_client.hset(
        "quests:1", "primeros-suministros", json.dumps({"status": "completed", "progress": [5]})
    )
    await deps.redis_client.hset(
        RedisKeys.player_inventory(1), mapping={f"slot_{i}": "38:20" for i in range(1, 31)}
    )
    result = await state.expansion.quests.command(
        1, "claim", {"quest": "primeros-suministros", "npc": npc.char_index}, operation_id()
    )
    assert not result["applied"]
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "gold") == "1000"
    assert (
        json.loads(await deps.redis_client.hget("quests:1", "primeros-suministros"))["status"]
        == "completed"
    )


@pytest.mark.asyncio
async def test_confirmed_kill_progress_and_prestige_are_deduplicated(world):
    """La instancia muerta produce un único evento, incluso con dos publicadores."""
    state, deps, _ = world
    npc = await quest_giver(deps)
    params = {"quest": "senderos-seguros", "npc": npc.char_index}
    await state.expansion.quests.command(1, "accept", params, operation_id())
    await deps.redis_client.hset(
        RedisKeys.player_user_stats(1), mapping={"faction_id": "royal", "faction_prestige": 24}
    )
    npc.npc_id, npc.instance_id, npc.hp, npc.is_hostile = 500, "confirmed-death", 0, True
    await deps.redis_client.hset(
        RedisKeys.npc_instance(npc.instance_id), mapping={"npc_id": 500, "hp": 0}
    )
    await asyncio.gather(*(state.expansion.quests.record_kill(npc, 1) for _ in range(2)))
    assert json.loads(await deps.redis_client.hget("quests:1", "senderos-seguros"))["progress"] == [
        1
    ]
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "faction_prestige") == "25"
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "faction_rank") == "1"


@pytest.mark.asyncio
async def test_barrier_two_hits_consume_one_shared_capacity(redis_client):
    """Ocho de daño contra cinco de barrera dejan tres de daño total."""
    await redis_client.hset(
        RedisKeys.player_user_stats(1),
        mapping={
            "min_hp": 100,
            "max_hp": 100,
            "barrier_capacity": 5,
            "barrier_until": time.time() + 30,
            "barrier_types": "physical",
        },
    )
    await asyncio.gather(
        *(apply_player_damage(redis_client.redis, 1, 4, operation_id()) for _ in range(2))
    )
    values = await redis_client.hgetall(RedisKeys.player_user_stats(1))
    assert values["min_hp"] == "97"
    assert values["barrier_capacity"] == "0"
    assert values["barrier_until"] == "0"


def test_expired_or_wrong_damage_type_does_not_absorb():
    """Una protección vencida o de otro tipo no convierte daño en inmunidad."""
    assert (
        absorb_damage(
            {"barrier_capacity": "9", "barrier_until": "1", "barrier_types": "magic"}, 5, "magic", 2
        )[0]
        == 5
    )
    assert absorb_damage(
        {"barrier_capacity": "9", "barrier_until": "10", "barrier_types": "physical"}, 5, "magic", 2
    ) == (5, {})


@pytest.mark.asyncio
async def test_periodic_parallel_ticks_do_not_duplicate_pulses(redis_client):
    """El marcador next participa en el mismo WATCH que HP y absorción."""
    row = {
        "mode": "damage",
        "amount": 4,
        "interval_seconds": 3,
        "until": time.time() + 30,
        "next": time.time() - 1,
        "identity": "fixture",
        "source": 2,
    }
    await redis_client.hset(
        RedisKeys.player_user_stats(1),
        mapping={"min_hp": 100, "max_hp": 100, "periodic_effects": json.dumps([row])},
    )
    await redis_client.hset(RedisKeys.player_position(1), mapping={"map": 2, "x": 50, "y": 50})
    await asyncio.gather(*(tick_periodic(redis_client.redis, 1) for _ in range(2)))
    assert await redis_client.hget(RedisKeys.player_user_stats(1), "min_hp") == "96"


@pytest.mark.asyncio
async def test_area_cost_components_and_effects_commit_once(world):
    """Dos víctimas comparten un solo gasto; repetir el recibo no vuelve a aplicarlo."""
    _, deps, _ = world
    for user in (1, 2, 3):
        await deps.player_repo.set_position(user, 50 + user, 50, 2, 3)
        await deps.redis_client.hset(
            RedisKeys.player_user_stats(user),
            mapping={"safe_mode": 0, "min_hp": 100, "max_hp": 100, "min_mana": 100, "min_sta": 100},
        )
    await deps.redis_client.hset(RedisKeys.player_spellbook(1), "1", "47")
    await deps.redis_client.hset(RedisKeys.player_inventory(1), "slot_1", "406:1")
    spell = {
        "id": 47,
        "min_damage": 5,
        "max_damage": 5,
        "mana_cost": 10,
        "stamina_cost": 3,
        "components": [{"item": 406, "quantity": 1}],
        "area": {"radius": 2, "max_targets": 8, "shape": "diamond", "targets": "players"},
    }
    request = CastRequest(1, 47, 52, 50, 1)
    plan = AreaSpellPlan(
        request,
        spell,
        PvpPolicy(),
        [CastRequest(1, 47, 52, 50, 1, 2), CastRequest(1, 47, 53, 50, 1, 3)],
    )
    identity = operation_id()
    with patch("src.services.combat.spell_plan.require_durable", new=AsyncMock()):
        first = await commit_spell(deps.redis_client.redis, identity, plan)
        assert first == await commit_spell(deps.redis_client.redis, identity, plan)
    assert first["applied"]
    assert len(first["area_results"]) == 2
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "min_mana") == "90"
    assert not await deps.redis_client.hget(RedisKeys.player_inventory(1), "slot_1")
    for user in (2, 3):
        assert await deps.redis_client.hget(RedisKeys.player_user_stats(user), "min_hp") == "95"


@pytest.mark.asyncio
async def test_missing_component_does_not_spend_or_damage(world):
    """Objetivo válido y maná suficiente no permiten ejecutar un hechizo gratis."""
    _, deps, _ = world
    for user in (1, 2):
        await deps.player_repo.set_position(user, 50 + user, 50, 2, 3)
        await deps.redis_client.hset(
            RedisKeys.player_user_stats(user),
            mapping={"safe_mode": 0, "min_mana": 100, "min_sta": 100},
        )
    await deps.redis_client.hset(RedisKeys.player_spellbook(1), "1", "50")
    spell = {
        "min_damage": 5,
        "max_damage": 5,
        "mana_cost": 10,
        "components": [{"item": 407, "quantity": 1}],
    }
    plan = SpellPlan(CastRequest(1, 50, 52, 50, 1, 2), spell, PvpPolicy())
    with patch("src.services.combat.spell_plan.require_durable", new=AsyncMock()):
        result = await commit_spell(deps.redis_client.redis, operation_id(), plan)
    assert not result["applied"]
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(1), "min_mana") == "100"
    assert await deps.redis_client.hget(RedisKeys.player_user_stats(2), "min_hp") == "100"


@pytest.mark.asyncio
async def test_clan_relations_and_concurrent_depot_withdrawal(world):
    """Dos líderes actualizan ambos clanes; un miembro no se arroga ese permiso."""
    state, deps, _ = world
    for user in (1, 2):
        clan = Clan(clan_id=user, name=f"Clan{user}", leader_id=user, leader_username=f"User{user}")
        clan.members[user] = ClanMember(
            user_id=user, username=f"User{user}", level=20, rank=ClanRank.LEADER
        )
        await deps.clan_repo.save_clan(clan)
    clans = state.expansion.clans
    for user, action, other, status in (
        (1, "propose", 2, "proposed"),
        (2, "accept", 1, "alliance"),
        (1, "cancel", 2, "none"),
        (1, "declare_war", 2, "war"),
        (2, "end_war", 1, "none"),
    ):
        result = await clans.relationship(user, action, {"clan": str(other)}, operation_id())
        assert result["applied"], result
        assert await deps.redis_client.hget("clan:relation:1:2", "state") == status
    await deps.redis_client.hset("clan:depot:1", "slot_1", "15:1")
    results = await asyncio.gather(
        *(
            clans.transfer(1, "withdraw", {"slot": 1, "item": 15, "quantity": 1}, operation_id())
            for _ in range(2)
        )
    )
    assert sum(row["applied"] for row in results) == 1
    assert await deps.inventory_repo.get_slot(1, 1) == (15, 1)
    assert not (await clans.relationship(3, "declare_war", {"clan": "2"}, operation_id()))[
        "applied"
    ]


@pytest.mark.asyncio
async def test_mute_scope_revocation_and_audit(world):
    """Un GM silencia canales explícitos; ni login ni acciones de juego se bloquean."""
    _, deps, _ = world
    await deps.redis_client.hset(RedisKeys.account_data("User1"), "is_gm", "1")
    with patch("src.security.chat_mutes.require_durable", new=AsyncMock()):
        assert (await moderate_chat(deps.account_repo, 1, "/MUTE User2 1 public,party prueba"))[
            "applied"
        ]
        assert await chat_rejection(deps.redis_client.redis, 2, "public")
        assert not await chat_rejection(deps.redis_client.redis, 2, "whisper")
        assert not (await moderate_chat(deps.account_repo, 3, "/UNMUTE User2 prueba"))["applied"]
        assert (await moderate_chat(deps.account_repo, 1, "/UNMUTE User2 corregido"))["applied"]
    assert not await chat_rejection(deps.redis_client.redis, 2, "public")
    assert len([key async for key in deps.redis_client.redis.scan_iter("moderation:audit:*")]) == 2
