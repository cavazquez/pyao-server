"""Clasificación exhaustiva del catálogo: cada objeto es elegible o tiene un motivo."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from math import isfinite
from typing import TYPE_CHECKING, Any

from src.models.item_types import ObjType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.models.item_catalog import ItemCatalog

MAX_QUANTITY = 100
MAX_WEIGHT = 100


@dataclass(frozen=True, slots=True)
class LootItemRule:
    """Categoría, calidad y exclusión explícita de un ID real del catálogo."""

    item_id: int
    category: str
    band: int
    power: float
    reason: str = ""


class LootCatalog:
    """Construye pools por categoría/banda una vez; el sorteo no recorre el catálogo."""

    def __init__(self, catalog: ItemCatalog, rules: dict[str, Any]) -> None:
        """Valida todas las categorías y clasifica todos los IDs existentes.

        Raises:
            ValueError: Si una categoría o un nuevo tipo de objeto carece de reglas.
        """
        self.categories: dict[str, Any] = rules["categories"]
        self.rules = rules
        self.catalog = catalog
        self.items: dict[int, LootItemRule] = {}
        pools: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
        for name, spec in self.categories.items():
            low, high = spec["quantity"]
            thresholds = spec["thresholds"]
            valid_thresholds = (
                len(thresholds) == len(rules["bands"]) - 1
                and all(isfinite(value) for value in thresholds)
                and all(a < b for a, b in pairwise(thresholds))
            )
            if not all(
                (
                    spec["slot"] in {"equipment", "consumable", "misc"},
                    0 < spec["weight"] <= MAX_WEIGHT,
                    1 <= low <= high <= MAX_QUANTITY,
                    valid_thresholds,
                    spec["metric"] in {"damage", "defense", "magic", "staff", "value"},
                )
            ):
                message = f"Categoría de loot inválida: {name}"
                raise ValueError(message)
        for item_id in catalog.get_all_item_ids():
            item = catalog.get_item_data(item_id)
            if item is None:
                message = f"Ítem {item_id} desapareció del catálogo durante la carga"
                raise ValueError(message)
            rule = self._classify(item_id, item)
            self.items[item_id] = rule
            if not rule.reason:
                pools[rule.category][rule.band].append(item_id)
        self.pools = {
            name: {band: tuple(sorted(ids)) for band, ids in bands.items()}
            for name, bands in pools.items()
        }

    def _category(self, item_id: int, item: dict[str, object]) -> str:
        override = self.rules["catalog"]["category_overrides"].get(str(item_id))
        if override:
            return str(override)
        obj_type = int(str(item["ObjType"]))
        if obj_type == ObjType.ARMAS:
            name = str(item["Name"]).casefold()
            if item_id in self.rules["catalog"]["tool_ids"]:
                return "tool"
            if int(str(item.get("StaffPower", 0))):
                return "staff"
            if int(str(item.get("Proyectil", 0))):
                return "bow"
            if name.startswith("daga"):
                return "dagger"
            if name.startswith("hacha"):
                return "axe"
            if name.startswith(("mazo", "mayal", "martillo", "garrote", "horquilla")):
                return "blunt"
            return "sword"
        if obj_type == ObjType.ANILLOS and int(str(item.get("Guante", 0))):
            return "glove"
        return str(self.rules["catalog"]["type_categories"].get(str(obj_type), ""))

    def _classify(self, item_id: int, item: dict[str, object]) -> LootItemRule:
        obj_type = int(str(item["ObjType"]))
        policy = self.rules["catalog"]
        reason = policy["excluded_items"].get(str(item_id), "")
        reason = reason or policy["excluded_types"].get(str(obj_type), "")
        if not reason and int(str(item.get("Agarrable", 0))) == 1:
            reason = "Objeto fijo: el catálogo prohíbe recogerlo (Agarrable=1)"
        if not reason and int(str(item.get("NoSeCae", item.get("Nosecae", 0)))):
            reason = "Recompensa ligada a su mecánica de entrega (NoSeCae=1)"
        if obj_type == ObjType.DINERO:
            reason = "Oro: se emite exclusivamente con la regla monetaria del NPC"
        if reason:
            return LootItemRule(item_id, "excluded", 0, 0, str(reason))
        category = self._category(item_id, item)
        if category not in self.categories:
            message = f"Ítem {item_id}, ObjType={obj_type}: falta una categoría de loot explícita"
            raise ValueError(message)
        spec = self.categories[category]
        power = self._power(item, spec["metric"])
        band = bisect_right(spec["thresholds"], power)
        minimum_level = int(str(item.get("MinLevel", 1)))
        for index, row in enumerate(self.rules["bands"]):
            if row["min_level"] <= minimum_level <= row["max_level"]:
                band = max(band, index)
                break
        else:
            message = f"Ítem {item_id}: MinLevel no pertenece a las bandas de loot"
            raise ValueError(message)
        return LootItemRule(item_id, category, band, power)

    @staticmethod
    def _power(item: dict[str, object], metric: str) -> float:
        if metric == "value":
            return float(str(item.get("Valor", item.get("sale_price", 0))))
        if metric == "staff":
            return max(
                float(str(item.get("StaffDamageBonus", 0))),
                float(str(item.get("StaffPower", 0))) * 10,
            )
        keys = {
            "damage": ("MinHit", "MaxHit"),
            "defense": ("MinDef", "MaxDef"),
            "magic": ("DefensaMagicaMin", "DefensaMagicaMax"),
        }[metric]
        return sum(float(str(item.get(key, 0))) for key in keys) / 2

    def choices(
        self, slot: str, band: int, allowed: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        """Categorías con probabilidad positiva, al menos un ID elegible y calidad válida.

        Returns:
            Nombres estables para un sorteo reproducible por instancia.
        """
        return tuple(
            name
            for name, spec in self.categories.items()
            if spec["slot"] == slot
            and (allowed is None or name in allowed)
            and any(tier <= band for tier in self.pools.get(name, {}))
        )
