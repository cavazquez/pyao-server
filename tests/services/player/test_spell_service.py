"""Plan de magia sin I/O: rechazos y estados que el commit debe conservar."""

import time
from copy import deepcopy

import pytest

from src.models.spell_catalog import SpellCatalog
from src.services.combat.pvp_policy import PvpPolicy
from src.services.combat.spell_plan import CastRequest, SpellPlan
from src.utils.redis_config import RedisKeys


@pytest.fixture
def planned_cast():
    """Congela un dardo sobre otro jugador en un mapa PvP permitido."""
    plan = SpellPlan(
        CastRequest(1, 2, 51, 50, 2, 2), dict(SpellCatalog().get_spell_data(2), id=2), PvpPolicy()
    )
    snapshot = {resource.key: {} for resource in plan.resources}
    for user in (1, 2):
        snapshot[RedisKeys.player_user_stats(user)] = {
            "min_hp": "100",
            "max_hp": "100",
            "min_mana": "100",
            "min_sta": "100",
            "safe_mode": "0",
        }
        snapshot[RedisKeys.player_position(user)] = {"map": "2", "x": str(49 + user), "y": "50"}
        snapshot[RedisKeys.player_stats(user)] = {"intelligence": "20"}
    snapshot[RedisKeys.player_spellbook(1)] = {"2": "2"}
    snapshot[RedisKeys.player_skills(1)] = {"level:magia": "100"}
    return plan, snapshot


@pytest.mark.parametrize(
    "case",
    [
        "empty_slot",
        "different_spell",
        "missing_source",
        "missing_target",
        "missing_position",
        "mana",
        "stamina",
        "dead_caster",
        "dead_target",
        "dumb",
        "skill",
        "range",
        "target_moved",
        "different_map",
        "safe_zone",
        "safe_source",
        "safe_target",
    ],
)
def test_rejected_cast_is_pure_and_has_no_writes(planned_cast, case):
    """Toda validación fallida deja intacto el snapshot y no propone ninguna mutación."""
    plan, snapshot = planned_cast
    source = snapshot[RedisKeys.player_user_stats(1)]
    target = snapshot[RedisKeys.player_user_stats(2)]
    source_position = snapshot[RedisKeys.player_position(1)]
    target_position = snapshot[RedisKeys.player_position(2)]
    if case == "empty_slot":
        snapshot[RedisKeys.player_spellbook(1)].clear()
    elif case == "different_spell":
        snapshot[RedisKeys.player_spellbook(1)]["2"] = "3"
    elif case == "missing_source":
        source.clear()
    elif case == "missing_target":
        target.clear()
    elif case == "missing_position":
        source_position.clear()
    elif case == "mana":
        source["min_mana"] = "0"
    elif case == "stamina":
        source["min_sta"] = "0"
    elif case == "dead_caster":
        source["min_hp"] = "0"
    elif case == "dead_target":
        target["min_hp"] = "0"
    elif case == "dumb":
        source["dumb_until"] = str(time.time() + 30)
    elif case == "skill":
        snapshot[RedisKeys.player_skills(1)]["level:magia"] = "0"
    elif case == "range":
        source_position["x"] = "1"
    elif case == "target_moved":
        target_position["x"] = "52"
    elif case == "different_map":
        target_position["map"] = "3"
    elif case == "safe_zone":
        source_position["map"] = target_position["map"] = "1"
    elif case == "safe_source":
        source["safe_mode"] = "1"
    elif case == "safe_target":
        target["safe_mode"] = "1"
    before = deepcopy(snapshot)
    result = plan.decide(snapshot)
    assert not result.result["applied"]
    assert result.writes == {}
    assert snapshot == before


def test_success_uses_catalog_cost_and_intelligence_bonus(planned_cast):
    """Daño, mana y stamina forman un solo plan, preservando campos ajenos."""
    plan, snapshot = planned_cast
    plan.base_amount = 5
    snapshot[RedisKeys.player_user_stats(1)]["gold"] = "123"
    result = plan.decide(snapshot)
    assert result.result["applied"]
    assert result.result["amount"] == 6
    assert result.writes[RedisKeys.player_user_stats(1)] == {
        "min_mana": "90",
        "min_sta": "99",
        "hidden_until": "0",
        "meditating": "0",
    }
    assert result.writes[RedisKeys.player_user_stats(2)]["min_hp"] == "94"
    assert snapshot[RedisKeys.player_user_stats(1)]["gold"] == "123"


def test_lethal_plan_marks_pending_life_with_legacy_hp_alias(planned_cast):
    """Una muerte se identifica en el mismo commit del daño y nunca deja un alias vivo."""
    plan, snapshot = planned_cast
    snapshot[RedisKeys.player_user_stats(2)].update({"hp": "1", "min_hp": "1", "life_id": "7"})
    plan.base_amount = 5
    result = plan.decide(snapshot)
    writes = result.writes[RedisKeys.player_user_stats(2)]
    assert writes["hp"] == "0"
    assert writes["min_hp"] == "0"
    assert writes["death_state"] == "pending"
    assert writes["life_id"] == "7"
    assert writes["death_map"] == "2"


def test_world_session_change_prevents_cost(planned_cast):
    """Un objetivo o sesión que cambió invalida la preparación sin gastar recursos."""
    plan, snapshot = planned_cast
    plan.world_guard = lambda: False
    assert plan.decide(snapshot).writes == {}
