"""Límites temporales, políticas completas y proyecciones inmutables del catálogo."""

import pytest

from src.items.condition import condition, effective
from src.items.ledger import new_state
from src.items.policy import individual, policies
from src.models.items_catalog import ITEMS_CATALOG
from src.utils.inventory_slot import InventorySlot
from src.utils.slot_plan import SlotPlan


@pytest.mark.parametrize(
    "item_id", [2, 15, 30, 128, 132, 659, 561, 562, 563, 1055, 1059, 1063, 1067, 1071]
)
def test_policy_preserves_graphics_and_only_scales_stats(item_id):
    """Un ejemplar conserva su tipo, gráficos, y estadísticas base sin mutarlas."""
    state = new_state("a" * 32, item_id, "player:1:inventory|slot_1", 100)
    state["uses_spent"] = str(int(state["max_uses"]) // 2)
    base = {"MinHit": 10, "MaxDef": 20, "Anim": 3, "Name": "Ejemplar"}
    assert effective(base, state, 100)["Anim"] == 3
    assert base == {"MinHit": 10, "MaxDef": 20, "Anim": 3, "Name": "Ejemplar"}
    assert 0 <= effective(base, state, 100)["MinHit"] <= 10
    assert individual(item_id)


@pytest.mark.parametrize(("maximum", "lifetime"), [(0, 0), (0, 100), (10, 0), (10, 100)])
def test_zero_disables_limits_and_time_never_rejuvenates(maximum, lifetime):
    """Usos y edad actúan independientemente; el reloj observado nunca retrocede."""
    state = new_state("b" * 32, 2, "x", 100)
    state.update(
        max_uses=str(maximum),
        lifetime_seconds=str(lifetime),
        expires_at=str(100 + lifetime),
        last_seen="150",
        uses_spent="5",
    )
    old = condition(state, 90)
    assert old == condition(state, 150)
    assert condition(state, 175)[0] <= old[0]
    if maximum:
        state["uses_spent"] = str(maximum)
        assert condition(state, 100) == (0, 0, True)
    elif lifetime:
        assert condition(state, 201) == (0, 0, True)
    else:
        assert condition(state, 10**9) == (10000, 10000, False)


def test_entire_catalog_has_an_explicit_policy():
    """No queda un tipo sin clasificar; el oro y los barcos no se rompen."""
    assert {item.obj_type for item in ITEMS_CATALOG.values()} <= policies().keys()
    assert policies()[5].kind == policies()[31].kind == "exempt"
    assert policies()[11].kind == "consumable"
    assert policies()[36].kind == "durable"


def test_individual_slots_cannot_stack_or_silently_lose_references():
    """Dos armas del mismo tipo conservan ejemplares separados."""
    first = InventorySlot(2, 1, ("a" * 32,))
    second = InventorySlot(2, 1, ("b" * 32,))
    assert not first.can_stack_with(second)
    assert first.add_quantity(1) == (first, 1)
    assert InventorySlot.parse(first.to_string()) == first
    plan = SlotPlan({"__item_instances__": "1", "slot_1": first.to_string()}, 2, 20)
    plan.give(2, 1, instance_ids=second.instance_ids)
    assert plan.slots == {1: first, 2: second}
    with pytest.raises(ValueError, match="espacio"):
        plan.give(2, 1)
    assert plan.slots == {1: first, 2: second}


def test_rounding_never_breaks_an_item_before_the_actual_limit():
    """Una fracción menor a un punto base sigue utilizable hasta el límite real."""
    state = new_state("c" * 32, 2, "x", 100)
    assert not condition(state, int(state["expires_at"]) - 1)[2]
    assert condition(state, int(state["expires_at"]))[2]
    state.update(max_uses="20000", lifetime_seconds="0", uses_spent="19999")
    assert not condition(state, 100)[2]
    state["uses_spent"] = "20000"
    assert condition(state, 100)[2]
