"""Regresiones de los 124 objetos fabricables y sus presupuestos económicos."""

from fractions import Fraction

import pytest

from src.economy.crafting_budget import economics, maximum_multiple
from src.models.crafting_data_loader import load_recipes


def test_all_recipes_fit_versioned_economic_budgets():
    """Fabricar conserva IDs/progresión y no recupera los márgenes desmedidos."""
    report = economics()
    recipes = {recipe["id"]: recipe for recipe in load_recipes()}
    assert report["version"] == 1
    assert len(report["recipes"]) == len(recipes) == 124
    for row in report["recipes"]:
        assert row["npc_sale"] <= row["material_sale"] * maximum_multiple(recipes[row["id"]])
        # La semilla artificial de mercaderes no contiene todos los insumos de ninguna receta.
        assert not row["all_inputs_sold_by_npc_seed"]
        assert row["scenarios"]
        for scenario in row["scenarios"]:
            assert scenario["expected_material_sale_cost"] >= row["material_sale"]
            assert set(scenario["npc_input_cost"]) == {"0", "50", "100"}


def test_boats_have_bounded_expected_margin_at_required_skill():
    """La carpintería naval mantiene ingreso por habilidad sin multiplicar oro por cien."""
    rows = {r["id"]: r for r in economics()["recipes"]}
    for item in (474, 475, 476):
        row = rows[f"carpinteria:{item}"]
        scenario = next(
            s for s in row["scenarios"] if s["skill"] == row["required"] and s["batch"] == 1
        )
        assert 0 < scenario["expected_npc_profit"] < row["material_sale"] * Fraction(1, 3)
        assert scenario["success_rate"] == pytest.approx(0.8)
