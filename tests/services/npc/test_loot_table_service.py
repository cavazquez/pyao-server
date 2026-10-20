"""Catálogo completo, probabilidades alcanzables y calidad real según nivel de NPC."""

import random
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

from src.models.item_catalog import ItemCatalog
from src.models.npc import NPC
from src.models.npc_catalog import NPCCatalog
from src.services.npc.loot_table_service import LootTableService


@pytest.fixture(scope="module")
def policy():
    """Carga la misma política y los mismos objetos usados por el servidor.

    Returns:
        Servicio de producción sin mocks del catálogo ni del sorteo.
    """
    return LootTableService()


def creature(level=2, profile="humanoid", **changes: object):
    """Construye una instancia muerta sin inferir el nivel a partir del atacante.

    Returns:
        NPC que usa exactamente los campos del contrato de producción.
    """
    return replace(
        NPC(
            npc_id=505,
            char_index=10001,
            instance_id="loot-fixture",
            map_id=2,
            x=50,
            y=50,
            heading=3,
            name="Goblin",
            description="Fixture",
            body_id=14,
            head_id=0,
            hp=0,
            max_hp=100,
            level=level,
            loot_profile=profile,
            is_hostile=True,
            is_attackable=True,
            gold_min=50000,
            gold_max=50000,
        ),
        **changes,
    )


def test_every_catalog_id_has_an_explicit_classification(policy):
    """Ningún ID nuevo puede quedar fuera de la auditoría por una lista de cuatro familias."""
    actual = ItemCatalog()
    assert set(policy.item_rules.items) == set(actual.get_all_item_ids())
    eligible = {i for i, row in policy.item_rules.items.items() if not row.reason}
    assert len(eligible) > 450
    assert {row.category for row in policy.item_rules.items.values() if not row.reason} == set(
        policy.item_rules.categories
    )
    reachable = set().union(
        *(policy.probabilities(band.min_level, "humanoid") for band in policy.bands)
    )
    assert reachable == eligible | {12}
    for item_id in eligible:
        rule = policy.item_rules.items[item_id]
        chance = policy.probabilities(policy.bands[rule.band].min_level, "humanoid")[item_id]
        assert 0 < chance <= 1


class TargetRandom(random.Random):
    """Fuerza las decisiones de selección sin sustituir la implementación de roll."""

    def __init__(self, item_id, category) -> None:
        """Conserva la categoría/ID objetivo; las cantidades siguen los límites reales."""
        super().__init__(0)
        self.item_id, self.category = item_id, category

    def random(self):
        """Acepta los slots y la banda actual.

        Returns:
            Extremo inferior del rango de azar permitido.
        """
        return 0.0

    def choices(self, population, weights=None, *, cum_weights=None, k=1):
        """Selecciona la categoría objetivo cuando pertenece al slot actual.

        Returns:
            Selección válida dentro de la población ofrecida por el servicio.
        """
        assert weights is None or all(weight > 0 for weight in weights)
        assert cum_weights is None
        return [self.category if self.category in population else population[0]] * k

    def choice(self, seq):
        """Selecciona el ID objetivo cuando está en el pool real recibido.

        Returns:
            Elemento que existe efectivamente en la secuencia del sorteo.
        """
        return self.item_id if self.item_id in seq else seq[0]


def test_roll_can_emit_every_eligible_catalog_id(policy):
    """Ejecuta roll para todos los elegibles; una probabilidad declarada sola no basta."""
    for item_id, rule in policy.item_rules.items.items():
        if rule.reason:
            continue
        npc = creature(policy.bands[rule.band].min_level)
        result = policy.roll(npc, rng=TargetRandom(item_id, rule.category))
        assert any(i == item_id and quantity > 0 for i, quantity in result), item_id


@pytest.mark.parametrize(
    "item_id",
    [2, 3, 15, 30, 36, 39, 138, 197, 400, 414, 474, 478, 697, 865, 873, 1055, 1081, 1082, 1083],
)
def test_all_normal_categories_are_eligible(policy, item_id):
    """Incluye otras armas, botas, guantes, barcos, pergaminos y herramientas reales."""
    assert not policy.item_rules.items[item_id].reason


@pytest.mark.parametrize("item_id", [4, 7, 13, 54, 188, 402, 556, 618, 625, 700])
def test_world_administrative_and_bound_items_have_reasons(policy, item_id):
    """Las exclusiones explican el caso y no pueden salir por otro pool."""
    assert policy.item_rules.items[item_id].reason
    assert all(item_id not in policy.probabilities(b.min_level, "boss") for b in policy.bands)


def test_quality_bands_have_strictly_better_category_stats(policy):
    """La mejora procede de daño, defensa o poder, no de cambiar el nombre o cantidad."""
    for category, bands in policy.item_rules.pools.items():
        if policy.item_rules.categories[category]["slot"] != "equipment":
            continue
        previous = None
        for tier in sorted(bands):
            powers = [policy.item_rules.items[i].power for i in bands[tier]]
            if previous is not None:
                assert min(powers) > previous, category
            previous = max(powers)


@pytest.mark.parametrize(
    ("level", "expected"),
    [(1, 0), (9, 0), (10, 1), (24, 1), (25, 2), (44, 2), (45, 3), (69, 3), (70, 4), (255, 4)],
)
def test_npc_level_boundaries(policy, level, expected):
    """Los cortes son inclusivos y proceden del nivel persistido del NPC."""
    assert policy.band_index(level) == expected


@pytest.mark.parametrize("level", [0, -1, 256])
def test_invalid_npc_levels_fail_closed(policy, level):
    """No se sustituyen niveles inválidos por el nivel del jugador."""
    with pytest.raises(ValueError, match="Nivel"):
        policy.roll(creature(level))


@pytest.mark.parametrize("kind", ["none", "tamed", "summoned"])
def test_no_drop_exceptions(policy, kind):
    """Los aldeanos, mascotas e invocaciones no sirven para fabricar oro o equipo."""
    npc = creature(
        profile="none" if kind == "none" else "humanoid",
        is_tamed=kind == "tamed",
        summoned_by_user_id=1 if kind == "summoned" else 0,
    )
    assert policy.roll(npc) == []


def test_beasts_drop_only_their_species_material(policy):
    """Un lobo no suelta armas ni oro, y conserva una probabilidad de no emitir piel."""
    npc = creature(10, "beast", loot_material=414)
    rng = random.Random(551)
    outcomes = [policy.roll(npc, rng=rng) for _ in range(1000)]
    assert 550 < sum(bool(row) for row in outcomes) < 750
    assert all(row in ([], [(414, 1)]) for row in outcomes)


def test_one_instance_always_reuses_the_same_roll(policy):
    """Repetir el sorteo de un UUID no permite cambiar los objetos tras una caída."""
    npc = creature(70)
    assert policy.roll(npc) == policy.roll(npc)
    assert all(
        policy.roll(replace(npc, instance_id=str(i)))
        == policy.roll(replace(npc, instance_id=str(i)))
        for i in range(100)
    )


@pytest.mark.parametrize("level", [2, 38, 100])
def test_distribution_matches_exact_probabilities_and_gold_ranges(policy, level):
    """Una muestra reproducible comprueba frecuencias, cantidades y la única emisión de oro."""
    rng = random.Random(20261020 + level)
    npc = creature(level)
    band = policy.bands[policy.band_index(level)]
    seen = Counter()
    gold_total = 0
    trials = 20000
    quantities = defaultdict(list)
    for _ in range(trials):
        result = policy.roll(npc, rng=rng)
        assert len(result) <= 4
        assert len([i for i, _ in result if i == 12]) <= 1
        for item_id, quantity in result:
            seen[item_id] += 1
            if item_id == 12:
                assert band.gold_min <= quantity <= band.gold_max
                gold_total += quantity
            else:
                rule = policy.item_rules.items[item_id]
                assert rule.band <= policy.band_index(level)
                low, high = policy.item_rules.categories[rule.category]["quantity"]
                assert low <= quantity <= high
                quantities[rule.category].append(quantity)
    expected = policy.probabilities(level, "humanoid")
    assert set(seen).issubset(expected)
    for item_id, probability in expected.items():
        sigma = (probability * (1 - probability) / trials) ** 0.5
        assert abs(seen[item_id] / trials - probability) <= 7 * sigma + 1 / trials
    expected_gold = 0.85 * (band.gold_min + band.gold_max) / 2
    assert abs(gold_total / trials - expected_gold) < max(1, expected_gold * 0.02)
    assert quantities


def test_every_npc_has_a_valid_profile_and_level(policy):
    """Audita IDs y niveles reales, incluidos aquellos mal nombrados en la tabla anterior."""
    catalog = NPCCatalog()
    for item in catalog._npcs.values():
        profile = item.get("loot_profile", "none")
        assert profile in policy.rules["profiles"]
        if profile != "none":
            assert 1 <= item["nivel"] <= 255
    for npc_id in (1, 4, 7, 10):
        assert policy.get_loot_for_npc(npc_id) == []


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("version = 2", "version = 7"),
        ("max_level = 9", "max_level = 8"),
        ("dagger = 15", "dagger = 99999"),
        ("sword = 164", "sword = 4"),
        ("misc_probability = 0.08", "misc_probability = nan"),
        ("weight = 18", "weight = 0"),
        ('"37" = "bag"', '"37" = "missing"'),
    ],
)
def test_corrupt_policy_prevents_startup(tmp_path, old, new):
    """El servidor no acepta huecos, IDs incorrectos, NaN o tipos sin política."""
    path = Path("data/npcs/loot_tables.toml")
    text = path.read_text(encoding="utf-8")
    assert old in text
    changed = tmp_path / "loot.toml"
    changed.write_text(text.replace(old, new))
    with pytest.raises(ValueError, match=r"loot|Política|Ítem|Categoría"):
        LootTableService(str(changed))


def test_real_armor_defense_uses_armor_type_not_tree_type(policy):
    """Las estadísticas de la armadura recogida llegan al cálculo real de defensa."""
    assert policy.catalog.get_armor_defense(30) == (10, 15)
    assert policy.catalog.get_armor_defense(481) == (60, 65)
    assert policy.catalog.get_armor_defense(4) is None


def test_profile_category_filter_is_shared_by_roll_and_report(tmp_path):
    """Un perfil específico no puede emitir objetos ajenos a sus categorías."""
    text = Path("data/npcs/loot_tables.toml").read_text(encoding="utf-8")
    text += (
        "\n[profiles.only_dagger]\ngold_probability=0.0\nequipment_multiplier=1.0\n"
        'consumable_probability=0.0\nmisc_probability=0.0\ncategories=["dagger"]\n'
    )
    path = tmp_path / "policy.toml"
    path.write_text(text, encoding="utf-8")
    service = LootTableService(str(path))
    npc = creature(1, "only_dagger")
    assert service.roll(npc, rng=TargetRandom(15, "dagger")) == [(15, 1)]
    assert set(service.probabilities(1, "only_dagger")) == {15}
    path.write_text(
        text.replace('categories=["dagger"]', 'categories=["unknown"]'), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="categorías inexistentes"):
        LootTableService(str(path))
