"""La auditoría versionada incluye todos los IDs y sigue la política efectiva."""

import json
from pathlib import Path

from src.operations.npc_loot_audit import report, serialize


def test_catalog_audit_is_complete_and_current():
    """Agregar un ítem o modificar su probabilidad exige actualizar el informe."""
    value = report()
    serialized = serialize(value)
    assert json.loads(serialized) == json.loads(json.dumps(value))
    assert len({row["id"] for row in value["items"]}) == value["items_total"]
    assert len(value["npcs"]) == value["npcs_total"]
    assert Path("docs/catalogs/npc-loot.json").read_text(encoding="utf-8") == serialized
