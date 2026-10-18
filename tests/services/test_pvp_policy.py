"""La misma política protege daño físico, magia y debuffs antes del commit."""

import pathlib
import tomllib

import pytest

from src.services.combat.pvp_policy import DEFAULT_SAFE_MAPS, PvpPolicy, is_hostile


@pytest.mark.parametrize(
    ("attacker", "target", "map_a", "map_b", "safe_a", "safe_b", "hp", "allowed"),
    [
        (1, 2, 2, 2, 0, 0, 100, True),
        (1, 1, 2, 2, 0, 0, 100, False),
        (1, 2, 2, 3, 0, 0, 100, False),
        (1, 2, 1, 1, 0, 0, 100, False),
        (1, 2, 2, 2, 1, 0, 100, False),
        (1, 2, 2, 2, 0, 1, 100, False),
        (1, 2, 2, 2, 0, 0, 0, False),
    ],
)
def test_shared_consent_policy(attacker, target, map_a, map_b, safe_a, safe_b, hp, *, allowed):
    """No hay excepciones por tipo de arma o fuente del daño."""
    policy = PvpPolicy()
    assert (
        policy.rejection(
            attacker,
            target,
            {"map": map_a},
            {"map": map_b},
            {"min_hp": 100, "safe_mode": safe_a},
            {"min_hp": hp, "safe_mode": safe_b},
        )
        is None
    ) is allowed


def test_policy_covers_every_safe_city():
    """Incluye las zonas seguras del dataset propio, sin sustituirlo por otro fork."""
    with pathlib.Path("data/world/cities.toml").open("rb") as stream:
        cities = tomllib.load(stream)["cities"]["city"]
    assert {city["map_id"] for city in cities if city.get("is_safe_zone")} <= set(DEFAULT_SAFE_MAPS)


def test_hostile_effects_and_beneficial_effects():
    """Daño, veneno y debuffs requieren PvP; curar y resucitar no lo requieren."""
    for spell in [
        {"min_damage": 2},
        {"poisons": True},
        {"immobilizes": True},
        {"id": 12},
        {"decreases_strength": True},
    ]:
        assert is_hostile(spell)
    for spell in [
        {"min_damage": 2, "heals_hp": True},
        {"revives": True},
        {"increases_strength": True},
    ]:
        assert not is_hostile(spell)
