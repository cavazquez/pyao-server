"""Botín por nivel del NPC: perfiles explícitos y un único sorteo reproducible por vida."""

import random
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.models.item_catalog import ItemCatalog
from src.runtime_paths import data_dir
from src.services.npc.loot_catalog import LootCatalog

if TYPE_CHECKING:
    from src.models.npc import NPC

FAMILIES = ("dagger", "sword", "shield", "armor")
FAMILY_TYPES = (2, 2, 16, 3)
POLICY_VERSION = 2
MAX_NPC_LEVEL = 255
MAX_EQUIPMENT_MULTIPLIER = 2.0


@dataclass(frozen=True, slots=True)
class LootBand:
    """Rango de nivel y calidad de cada familia de equipo."""

    min_level: int
    max_level: int
    gold_min: int
    gold_max: int
    equipment_probability: float
    equipment: tuple[int, ...]


class LootTableService:
    """Valida el catálogo antes de aceptar jugadores; no ignora una política corrupta."""

    def __init__(
        self, loot_tables_path: str | None = None, *, catalog: ItemCatalog | None = None
    ) -> None:
        """Carga exclusivamente la política versionada y los IDs reales de objetos.

        Raises:
            ValueError: Si un perfil referencia categorías inexistentes o vacías.
        """
        self.catalog = catalog or ItemCatalog()
        path = Path(loot_tables_path) if loot_tables_path else data_dir() / "npcs/loot_tables.toml"
        self.rules: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
        self.bands = tuple(
            LootBand(
                row["min_level"],
                row["max_level"],
                row["gold_min"],
                row["gold_max"],
                float(row["equipment_probability"]),
                tuple(row[key] for key in FAMILIES),
            )
            for row in self.rules["bands"]
        )
        self._validate()
        self.item_rules = LootCatalog(self.catalog, self.rules)
        for name, profile in self.rules["profiles"].items():
            if "categories" in profile and (
                not profile["categories"]
                or not set(profile["categories"]).issubset(self.item_rules.categories)
            ):
                message = f"Perfil de loot {name}: categorías inexistentes o vacías"
                raise ValueError(message)

    def _validate(self) -> None:
        """Rechaza huecos, IDs inexistentes, tipos incorrectos o probabilidades inválidas.

        Raises:
            ValueError: Si la política no es compatible o pierde progresión de stats.
        """
        valid = (
            self.rules.get("version") == POLICY_VERSION
            and self.bands
            and self.bands[0].min_level == 1
            and self.bands[-1].max_level == MAX_NPC_LEVEL
            and 0 <= self.rules["current_band_probability"] <= 1
        )
        previous = 0
        previous_stats = [0.0] * len(FAMILIES)
        for band in self.bands:
            valid = valid and (
                band.min_level == previous + 1
                and band.min_level <= band.max_level
                and 0 <= band.gold_min <= band.gold_max
                and 0 <= band.equipment_probability <= 1
            )
            previous = band.max_level
            for index, (item_id, obj_type) in enumerate(
                zip(band.equipment, FAMILY_TYPES, strict=True)
            ):
                item = self.catalog.get_item_data(item_id) or {}
                minimum, maximum = (
                    ("MinHit", "MaxHit") if obj_type == FAMILY_TYPES[0] else ("MinDef", "MaxDef")
                )
                power = (int(str(item.get(minimum, 0))) + int(str(item.get(maximum, 0)))) / 2
                valid = valid and item.get("ObjType") == obj_type and power > previous_stats[index]
                previous_stats[index] = power
        for profile in self.rules["profiles"].values():
            valid = (
                valid
                and all(
                    0 <= float(value) <= 1
                    for key, value in profile.items()
                    if key.endswith("probability")
                )
                and 0 <= float(profile["equipment_multiplier"]) <= MAX_EQUIPMENT_MULTIPLIER
            )
        if not valid:
            message = (
                "Política de loot inválida: bandas/IDs/probabilidades/calidad deben ser coherentes"
            )
            raise ValueError(message)

    def band_index(self, level: int) -> int:
        """Busca la banda del NPC sin aceptar un nivel enviado por el cliente.

        Returns:
            Índice de la banda configurada.

        Raises:
            ValueError: Si el nivel persistido no es válido.
        """
        for index, band in enumerate(self.bands):
            if band.min_level <= level <= band.max_level:
                return index
        message = "Nivel de NPC fuera de las bandas de loot"
        raise ValueError(message)

    def roll(self, npc: NPC, *, rng: random.Random | None = None) -> list[tuple[int, int]]:
        """Sortea oro, equipo, consumibles y otros objetos de todo el catálogo elegible.

        Returns:
            Objetos/cantidades; un mismo UUID y política producen el mismo sorteo.

        Raises:
            ValueError: Ante perfiles o materiales persistidos desconocidos.
        """
        if npc.summoned_by_user_id or npc.is_tamed or npc.loot_profile == "none":
            return []
        if npc.loot_profile not in self.rules["profiles"]:
            message = "Perfil de loot de NPC desconocido"
            raise ValueError(message)
        index = self.band_index(npc.level)
        band, profile = self.bands[index], self.rules["profiles"][npc.loot_profile]
        rng = rng or random.Random(f"npc-loot-v{POLICY_VERSION}:{npc.instance_id}")
        result: list[tuple[int, int]] = []
        if rng.random() < profile["gold_probability"]:
            amount = rng.randint(band.gold_min, band.gold_max)
            if amount:
                result.append((12, amount))
        for slot, chance in self._slot_probabilities(index, profile).items():
            if rng.random() < chance:
                categories = self.item_rules.choices(slot, index, profile.get("categories"))
                if not categories:
                    continue
                category = rng.choices(
                    categories,
                    weights=[self.item_rules.categories[name]["weight"] for name in categories],
                    k=1,
                )[0]
                quality = (
                    index
                    if rng.random() < self.rules["current_band_probability"]
                    else max(0, index - 1)
                )
                ids = self._pool(category, index, quality)
                low, high = self.item_rules.categories[category]["quantity"]
                result.append((rng.choice(ids), rng.randint(low, high)))
        if npc.loot_material:
            if not self.catalog.item_exists(npc.loot_material):
                message = "Material de loot inexistente"
                raise ValueError(message)
            if rng.random() < profile.get("material_probability", 0):
                result.append((npc.loot_material, 1))
        return result

    def _slot_probabilities(self, index: int, profile: dict[str, Any]) -> dict[str, float]:
        return {
            "equipment": min(
                1.0, self.bands[index].equipment_probability * profile["equipment_multiplier"]
            ),
            "consumable": float(profile["consumable_probability"]),
            "misc": float(profile["misc_probability"]),
        }

    def _pool(self, category: str, band: int, quality: int) -> tuple[int, ...]:
        pools = self.item_rules.pools[category]
        available = [tier for tier in pools if tier <= band]
        tier = max((tier for tier in available if tier <= quality), default=min(available))
        return pools[tier]

    def probabilities(self, level: int, profile_name: str) -> dict[int, float]:
        """Probabilidad exacta por ID, sin estimarla con una simulación aleatoria.

        Returns:
            Probabilidad de emitir cada ID por muerte, excluidos materiales de especie.
        """
        index = self.band_index(level)
        profile = self.rules["profiles"][profile_name]
        result = {12: float(profile["gold_probability"])}
        current = float(self.rules["current_band_probability"])
        for slot, chance in self._slot_probabilities(index, profile).items():
            categories = self.item_rules.choices(slot, index, profile.get("categories"))
            total_weight = sum(self.item_rules.categories[name]["weight"] for name in categories)
            for category in categories:
                weight = self.item_rules.categories[category]["weight"] / total_weight
                for tier, probability in ((index, current), (max(0, index - 1), 1 - current)):
                    ids = self._pool(category, index, tier)
                    for item_id in ids:
                        result[item_id] = result.get(
                            item_id, 0
                        ) + chance * weight * probability / len(ids)
        return {item_id: probability for item_id, probability in result.items() if probability > 0}

    def get_loot_for_npc(self, npc_id: int) -> list[tuple[int, int]]:
        """Adaptador de herramientas; el juego usa roll con el UUID de la instancia.

        Returns:
            Sorteo para una instancia efímera del catálogo, o vacío si no existe.
        """
        from src.models.npc import NPC  # ruff: ignore[import-outside-top-level]
        from src.models.npc_catalog import NPCCatalog  # ruff: ignore[import-outside-top-level]

        row = NPCCatalog().get_npc_data(npc_id)
        if row is None:
            return []
        npc = NPC(
            npc_id=npc_id,
            char_index=10001,
            instance_id=str(random.getrandbits(128)),
            map_id=1,
            x=50,
            y=50,
            heading=3,
            name=str(row.get("nombre", "")),
            description="",
            body_id=0,
            head_id=0,
            hp=0,
            max_hp=int(str(row.get("hp_max", 0))),
            level=int(str(row.get("nivel", 1))),
            is_hostile=bool(row.get("es_hostil")),
            is_attackable=bool(row.get("es_atacable")),
            loot_profile=str(row.get("loot_profile", "none")),
            loot_material=int(str(row.get("loot_material", 0))),
        )
        return self.roll(npc)
