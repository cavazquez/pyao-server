"""Presupuestos versionados del catálogo completo, con pérdidas y oportunidad."""

import json
import math
import tomllib
from fractions import Fraction
from typing import Any

from src.models.crafting_data_loader import load_recipes
from src.models.item_catalog import ItemCatalog
from src.runtime_paths import data_dir
from src.services.npc_trade_plan import commerce_price

BUDGET_VERSION = 1
BOAT_IDS = frozenset({474, 475, 476})
SKILL_SAMPLES = (0, 50, 100)
BATCH_SAMPLES = (1, 100)
CRAFT_INTERVAL_SECONDS = Fraction(1, 2)
CARPENTRY_BUDGETS = (
    (30, Fraction(12, 10)),
    (60, Fraction(13, 10)),
    (90, Fraction(14, 10)),
    (100, Fraction(15, 10)),
)


def maximum_multiple(recipe: dict[str, Any]) -> Fraction:
    """Acota el ingreso bruto por familia, conservando la recompensa de fundición.

    Returns:
        Tope sobre el valor NPC de los materiales a habilidad máxima y sin fallos.
    """
    if recipe["id"].startswith("fundir:"):
        return Fraction(18)
    if recipe["skill"] == "herreria":
        return Fraction(1)
    required = int(recipe["required"])
    return next(budget for ceiling, budget in CARPENTRY_BUDGETS if required <= ceiling)


def economics() -> dict[str, Any]:
    """Calcula todas las recetas sin modificar precios, saldos ni reglas de juego.

    Returns:
        Informe reproducible, con fracciones exactas antes de redondear la salida.
    """
    catalog = ItemCatalog()
    initial = tomllib.loads((data_dir() / "npcs/merchants.toml").read_text())
    sold_inputs = {
        item["item_id"] for merchant in initial["merchant"] for item in merchant.get("item", [])
    }

    def value(item_id: int) -> int:
        return int(str((catalog.get_item_data(item_id) or {}).get("Valor", 0)))

    rows = []
    for recipe in load_recipes():
        materials = recipe["materials"]
        sale = value(recipe["item_id"]) // 2
        opportunity = sum(value(m["item_id"]) // 2 * m["quantity"] for m in materials)
        scenarios = []
        for level in sorted({*SKILL_SAMPLES, recipe["required"]}):
            if level < recipe["required"]:
                continue
            probability = Fraction(
                min(100, recipe["success_rate"] + (level - recipe["required"]) // 2), 100
            )
            for batch in BATCH_SAMPLES:
                lost = sum(
                    value(m["item_id"]) // 2 * math.ceil(m["quantity"] * batch / 2)
                    for m in materials
                )
                expected = opportunity * batch + (1 - probability) / probability * lost
                scenarios.append(
                    {
                        "skill": level,
                        "batch": batch,
                        "success_rate": float(probability),
                        "expected_material_sale_cost": round(float(expected / batch), 4),
                        "expected_npc_profit": round(float(sale - expected / batch), 4),
                        "minimum_craft_seconds_per_item": round(
                            float(CRAFT_INTERVAL_SECONDS / probability / batch), 4
                        ),
                        "npc_input_cost": {
                            str(commerce): sum(
                                commerce_price(value(m["item_id"]), commerce, "buy") * m["quantity"]
                                for m in materials
                            )
                            for commerce in SKILL_SAMPLES
                        },
                    }
                )
        rows.append(
            {
                "id": recipe["id"],
                "name": recipe["name"],
                "required": recipe["required"],
                "family": "boats" if recipe["item_id"] in BOAT_IDS else recipe["skill"],
                "purpose": "npc_sale_and_player_market"
                if sale > opportunity
                else "progression_own_use_and_player_market",
                "npc_sale": sale,
                "material_sale": opportunity,
                "gross_multiple": round(sale / max(1, opportunity), 6),
                "maximum_multiple": float(maximum_multiple(recipe)),
                "all_inputs_sold_by_npc_seed": all(m["item_id"] in sold_inputs for m in materials),
                "scenarios": scenarios,
            }
        )
    return {
        "version": BUDGET_VERSION,
        "reference_work_seconds": float(CRAFT_INTERVAL_SECONDS),
        "collection_time_included": False,
        "recipes": rows,
    }


if __name__ == "__main__":
    print(json.dumps(economics(), ensure_ascii=False, indent=2))
