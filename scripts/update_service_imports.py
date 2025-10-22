"""Script para actualizar imports de services."""

from pathlib import Path

# Mapeo de imports
IMPORT_REPLACEMENTS = {
    # player/
    "from src.authentication_service import": "from src.services.player.authentication_service import",
    "from src.player_service import": "from src.services.player.player_service import",
    "from src.equipment_service import": "from src.services.player.equipment_service import",
    "from src.stamina_service import": "from src.services.player.stamina_service import",
    "from src.spell_service import": "from src.services.player.spell_service import",
    
    # npc/
    "from src.npc_service import": "from src.services.npc.npc_service import",
    "from src.npc_ai_service import": "from src.services.npc.npc_ai_service import",
    "from src.npc_death_service import": "from src.services.npc.npc_death_service import",
    "from src.npc_respawn_service import": "from src.services.npc.npc_respawn_service import",
    "from src.loot_table_service import": "from src.services.npc.loot_table_service import",
    
    # combat/
    "from src.combat_service import": "from src.services.combat.combat_service import",
    "from src.combat_weapon_service import": "from src.services.combat.combat_weapon_service import",
    
    # map/
    "from src.map_resources_service import": "from src.services.map.map_resources_service import",
    "from src.map_transition_service import": "from src.services.map.map_transition_service import",
    "from src.player_map_service import": "from src.services.map.player_map_service import",
    "from src.pathfinding_service import": "from src.services.map.pathfinding_service import",
    
    # root services/
    "from src.commerce_service import": "from src.services.commerce_service import",
    "from src.multiplayer_broadcast_service import": "from src.services.multiplayer_broadcast_service import",
}


def update_imports_in_file(file_path: Path) -> bool:
    """Actualiza imports en un archivo."""
    content = file_path.read_text()
    original_content = content

    for old_import, new_import in IMPORT_REPLACEMENTS.items():
        content = content.replace(old_import, new_import)

    if content != original_content:
        file_path.write_text(content)
        return True
    return False


def update_all_imports() -> None:
    """Actualiza imports en todos los archivos."""
    updated_count = 0
    
    # Actualizar en src/
    print("📝 Actualizando imports en src/...")
    for py_file in Path("src").rglob("*.py"):
        if update_imports_in_file(py_file):
            updated_count += 1
            print(f"  ✓ {py_file.relative_to('.')}")
    
    # Actualizar en tests/
    print("\n📝 Actualizando imports en tests/...")
    for py_file in Path("tests").glob("*.py"):
        if update_imports_in_file(py_file):
            updated_count += 1
            print(f"  ✓ {py_file.name}")
    
    print(f"\n✅ {updated_count} archivos actualizados")


if __name__ == "__main__":
    update_all_imports()
