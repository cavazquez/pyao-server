"""Informe reproducible de todos los objetos y NPCs de la política efectiva de botín."""

import argparse
import json
from pathlib import Path
from typing import Any

from src.models.npc_catalog import NPCCatalog
from src.services.npc.loot_table_service import LootTableService

STATS = (
    "MinHit",
    "MaxHit",
    "MinDef",
    "MaxDef",
    "StaffPower",
    "StaffDamageBonus",
    "DefensaMagicaMin",
    "DefensaMagicaMax",
    "TipoPocion",
    "EffectDurationSeconds",
    "MinModificador",
    "MaxModificador",
    "MinHP",
    "MinHam",
    "MinHAM",
    "MinAgu",
    "HechizoIndex",
    "Valor",
)
RESTRICTIONS = (
    "AllowedClasses",
    "ClasesProhibidas",
    "MinLevel",
    "MinSkill",
    "Hombre",
    "Mujer",
    "RazaEnana",
    "Razaenana",
    "RazaDrow",
    "Real",
    "Caos",
    "Newbie",
    "newbie",
    "NoSeCae",
    "Nosecae",
    "Agarrable",
)


def report() -> dict[str, Any]:
    """Incluye cada ID una sola vez y probabilidades exactas de cada banda/perfil.

    Returns:
        Informe sin muestreos, Redis, credenciales ni datos de jugadores.
    """
    policy, catalog = LootTableService(), NPCCatalog()
    items, npcs = [], []
    for item_id, rule in policy.item_rules.items.items():
        raw = policy.catalog.get_item_data(item_id) or {}
        spec = policy.item_rules.categories.get(rule.category, {})
        items.append(
            {
                "id": item_id,
                "name": raw["Name"],
                "type": raw["ObjType"],
                "category": rule.category,
                "minimum_npc_level": None if rule.reason else policy.bands[rule.band].min_level,
                "quality_metric": spec.get("metric"),
                "quality": rule.power,
                "quantity": spec.get("quantity"),
                "exclusion": rule.reason or None,
                "stats": {key: raw[key] for key in STATS if key in raw},
                "restrictions": {key: raw[key] for key in RESTRICTIONS if key in raw},
            }
        )
    for npc_id in sorted(catalog.get_all_npc_ids()):
        raw = catalog.get_npc_data(npc_id) or {}
        profile = str(raw.get("loot_profile", "none"))
        level = int(str(raw.get("nivel", 1)))
        band = policy.bands[policy.band_index(level)] if profile != "none" else None
        npcs.append(
            {
                "id": npc_id,
                "name": raw.get("nombre"),
                "level": level,
                "profile": profile,
                "species_material": raw.get("loot_material", 0),
                "gold_probability": policy.rules["profiles"][profile]["gold_probability"],
                "gold_range": [band.gold_min, band.gold_max] if band else [0, 0],
                "no_loot_reason": "Perfil explícito sin recompensa" if profile == "none" else None,
            }
        )
    return {
        "version": policy.rules["version"],
        "items_total": len(items),
        "eligible": sum(not row["exclusion"] for row in items),
        "npcs_total": len(npcs),
        "profiles": policy.rules["profiles"],
        "bands": policy.rules["bands"],
        "notes": [
            "Oro ID12 excluido de pools de objetos: usa una única regla monetaria.",
            "Las probabilidades son por ID y muerte; no dependen del nivel del jugador.",
            (
                "La cantidad es uniforme en el rango; como máximo un resultado por slot "
                "(equipo, consumible, otros)."
            ),
            "Mascotas e invocaciones no emiten botín ni experiencia.",
            "La piel de especie tiene probabilidad separada, sólo en bestias configuradas.",
            (
                "Los niveles inferidos de HP son un balance propio de PyAO; "
                "no son niveles del AO original."
            ),
        ],
        "items": items,
        "npcs": npcs,
        "probabilities": {
            profile: {
                str(band.min_level): policy.probabilities(band.min_level, profile)
                for band in policy.bands
            }
            for profile in policy.rules["profiles"]
        },
    }


def serialize(value: dict[str, Any]) -> str:
    """Mantiene un objeto por línea para poder revisar cambios de IDs con Git.

    Returns:
        JSON válido y estable sin un diff de decenas de miles de líneas.
    """
    encoded = json.dumps(value, ensure_ascii=False, indent=2)
    for key in ("items", "npcs"):
        formatted = json.dumps(value[key], ensure_ascii=False, indent=2)
        compact = (
            "[\n"
            + ",\n".join("    " + json.dumps(row, ensure_ascii=False) for row in value[key])
            + "\n  ]"
        )
        indented = formatted.replace("\n", "\n  ")
        encoded = encoded.replace(indented, compact, 1)
    return encoded + "\n"


def main() -> None:
    """Genera la auditoría o comprueba que el informe versionado sigue actualizado."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = report()
    text = serialize(value)
    if args.check:
        if args.output is None or args.output.read_text(encoding="utf-8") != text:
            parser.exit(1, "El informe de botín está desactualizado; volver a generarlo.\n")
    elif args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if args.output:
        print(
            json.dumps(
                {
                    "items": value["items_total"],
                    "eligible": value["eligible"],
                    "npcs": value["npcs_total"],
                    "checked": args.check,
                }
            )
        )


if __name__ == "__main__":
    main()
