"""Especialidades explícitas del catálogo efectivo, independientes del nombre."""

from typing import cast

from src.models.npc_catalog import NPCCatalog


def merchant_rules() -> dict[int, frozenset[int]]:
    """Lee tipos aceptados de los NPCs propios ya normalizados.

    Returns:
        ID de mercader a tipos permitidos; una lista vacía rechaza la venta.
    """
    catalog = NPCCatalog()
    return {
        npc_id: frozenset(
            int(value) for value in cast("list[int]", data.get("accepted_obj_types", []))
        )
        for npc_id, data in catalog._npcs.items()  # ruff: ignore[private-member-access] - adaptador del catálogo propio.
        if data.get("es_mercader")
    }
