"""Script para reorganizar services en subcarpetas por categoría."""

import subprocess
from pathlib import Path


def reorganize_services() -> None:
    """Reorganiza services en subcarpetas."""
    src_dir = Path("src")
    services_dir = src_dir / "services"

    # Crear estructura de carpetas
    print("📁 Creando estructura de services...")
    services_dir.mkdir(exist_ok=True)
    
    # Subcarpetas por categoría
    categories = {
        "player": "Servicios relacionados con jugadores",
        "npc": "Servicios de NPCs e IA",
        "combat": "Servicios de combate",
        "map": "Servicios de mapas",
    }
    
    for category, description in categories.items():
        category_dir = services_dir / category
        category_dir.mkdir(exist_ok=True)
        (category_dir / "__init__.py").write_text(f'"""{description}."""\n')
        print(f"  ✓ services/{category}/")
    
    (services_dir / "__init__.py").write_text('"""Package de services (lógica de negocio)."""\n')

    # Mapeo de services a categorías
    service_mapping = {
        # player/
        "authentication_service.py": "player",
        "player_service.py": "player",
        "equipment_service.py": "player",
        "stamina_service.py": "player",
        "spell_service.py": "player",
        
        # npc/
        "npc_service.py": "npc",
        "npc_ai_service.py": "npc",
        "npc_death_service.py": "npc",
        "npc_respawn_service.py": "npc",
        "loot_table_service.py": "npc",
        
        # combat/
        "combat_service.py": "combat",
        "combat_weapon_service.py": "combat",
        
        # map/
        "map_resources_service.py": "map",
        "map_transition_service.py": "map",
        "player_map_service.py": "map",
        "pathfinding_service.py": "map",
        
        # root (no category - services generales)
        "commerce_service.py": None,  # Se queda en services/
        "multiplayer_broadcast_service.py": None,  # Se queda en services/
    }

    # Mover services a categorías
    print("\n📦 Moviendo services...")
    moved_count = 0
    
    for service_file, category in sorted(service_mapping.items()):
        src_file = src_dir / service_file
        if src_file.exists():
            if category:
                dest_file = services_dir / category / service_file
                print(f"  ✓ {service_file} → services/{category}/")
            else:
                dest_file = services_dir / service_file
                print(f"  ✓ {service_file} → services/")
            
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            moved_count += 1

    print(f"\n✅ Reorganización completada: {moved_count} archivos movidos")
    print(f"📂 Categorías creadas: {len(categories)}")
    print("\n⚠️  SIGUIENTE PASO: Actualizar imports")


if __name__ == "__main__":
    reorganize_services()
