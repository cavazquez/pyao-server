"""Clasificación explícita de costas y portales con cambio de medio."""

from __future__ import annotations

from typing import Any


def classify(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Conserva los enlaces originales y declara su política de navegación.

    Returns:
        Cada candidato y su clasificación geométrica revisable, sin crear inversas.
    """
    candidates = []
    for row in rows:
        if row["source_water"] == row["destination_water"]:
            continue
        edge = row["x"] <= 9 or row["x"] >= 92 or row["y"] <= 7 or row["y"] >= 94
        candidates.append(
            {
                "source": [row["from_map"], row["x"], row["y"]],
                "destination": [row["to_map"], row["to_x"], row["to_y"]],
                "classification": "coast_boundary" if edge else "interior_portal",
                "basis": "authored edge coordinate"
                if edge
                else "authored interior exit coordinate",
                "source_water": row["source_water"],
                "destination_water": row["destination_water"],
                "policy": "require_living_character_valid_boat_and_navigation"
                if row["destination_water"]
                else "disembark_atomically_keep_boat_in_inventory",
            }
        )
    return {
        "version": 1,
        "note": "Geometric classification of authored data; interior portals do not waive boat requirements. No new reverse routes.",
        "count": len(candidates),
        "routes": candidates,
    }
