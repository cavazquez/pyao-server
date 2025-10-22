"""Script para reorganizar tests siguiendo estructura de src/."""

import subprocess
from pathlib import Path


def reorganize_tests() -> None:
    """Reorganiza tests en subcarpetas."""
    tests_dir = Path("tests")
    
    # Crear estructura
    print("📁 Creando estructura de tests...")
    
    categories = {
        "tasks": "Tests de tasks",
        "repositories": "Tests de repositories",
        "services": "Tests de services", 
        "messaging": "Tests de messaging",
        "models": "Tests de models",
        "integration": "Tests de integración",
        "unit": "Tests unitarios",
    }
    
    for category, description in categories.items():
        category_dir = tests_dir / category
        category_dir.mkdir(exist_ok=True)
        (category_dir / "__init__.py").write_text(f'"""{description}."""\n')
        print(f"  ✓ tests/{category}/")
    
    # Subcarpetas de tasks (espejar src/tasks/)
    task_categories = ["player", "inventory", "commerce", "banking", "spells", "interaction", "work", "admin"]
    for task_cat in task_categories:
        task_dir = tests_dir / "tasks" / task_cat
        task_dir.mkdir(exist_ok=True, parents=True)
        (task_dir / "__init__.py").write_text(f'"""Tests de tasks/{task_cat}."""\n')
        print(f"  ✓ tests/tasks/{task_cat}/")
    
    # Subcarpetas de services (espejar src/services/)
    service_categories = ["player", "npc", "combat", "map"]
    for svc_cat in service_categories:
        svc_dir = tests_dir / "services" / svc_cat
        svc_dir.mkdir(exist_ok=True, parents=True)
        (svc_dir / "__init__.py").write_text(f'"""Tests de services/{svc_cat}."""\n')
        print(f"  ✓ tests/services/{svc_cat}/")

    # Mapeo de tests a categorías
    test_mapping = {
        # Tasks - player
        "test_task_login.py": "tasks/player",
        "test_task_attack.py": "tasks/player",
        "test_task_walk.py": "tasks/player",
        "test_task_change_heading.py": "tasks/player",
        "test_task_meditate.py": "tasks/player",
        
        # Tasks - inventory
        "test_task_inventory_click.py": "tasks/inventory",
        "test_task_equip_item.py": "tasks/inventory",
        "test_task_drop.py": "tasks/inventory",
        "test_task_double_click.py": "tasks/inventory",
        
        # Tasks - commerce
        "test_task_commerce_buy.py": "tasks/commerce",
        "test_task_commerce_sell.py": "tasks/commerce",
        "test_task_commerce_end.py": "tasks/commerce",
        
        # Tasks - banking
        "test_task_bank_deposit.py": "tasks/banking",
        "test_task_bank_extract.py": "tasks/banking",
        "test_task_bank_deposit_gold.py": "tasks/banking",
        "test_task_bank_extract_gold.py": "tasks/banking",
        
        # Tasks - spells
        "test_task_cast_spell.py": "tasks/spells",
        "test_spell_targeting.py": "tasks/spells",
        
        # Tasks - interaction
        "test_task_left_click.py": "tasks/interaction",
        "test_task_information.py": "tasks/interaction",
        
        # Tasks - otros (unit por ahora)
        "test_task_pickup.py": "unit",
        "test_task_attributes.py": "unit",
        "test_task_request_position_update.py": "unit",
        "test_task_factory.py": "unit",
        
        # Repositories
        "test_account_repository.py": "repositories",
        "test_bank_repository.py": "repositories",
        "test_equipment_repository.py": "repositories",
        "test_ground_items_repository.py": "repositories",
        "test_inventory_repository.py": "repositories",
        "test_merchant_repository.py": "repositories",
        "test_npc_repository.py": "repositories",
        "test_player_repository.py": "repositories",
        "test_server_repository.py": "repositories",
        "test_spellbook_repository.py": "repositories",
        
        # Services - player
        "test_authentication_service.py": "services/player",
        "test_player_service.py": "services/player",
        "test_equipment_service.py": "services/player",
        "test_stamina_service.py": "services/player",
        
        # Services - npc
        "test_npc_death_service.py": "services/npc",
        "test_npc_ai_configurable.py": "services/npc",
        "test_loot_table_service.py": "services/npc",
        
        # Services - combat
        "test_combat_service.py": "services/combat",
        "test_combat_weapon_service.py": "services/combat",
        
        # Services - general
        "test_service_initializer.py": "services",
        
        # Messaging
        "test_message_sender.py": "messaging",
        "test_message_audio_sender.py": "messaging",
        "test_message_character_sender.py": "messaging",
        "test_message_console_sender.py": "messaging",
        "test_message_inventory_sender.py": "messaging",
        "test_message_map_sender.py": "messaging",
        "test_message_player_stats_sender.py": "messaging",
        "test_message_session_sender.py": "messaging",
        "test_message_visual_effects_sender.py": "messaging",
        
        # Models
        "test_item.py": "models",
        "test_item_types.py": "models",
        "test_items_catalog.py": "models",
        "test_npc_factory.py": "models",
        "test_spell_catalog.py": "models",
        
        # Integration tests (flujos completos)
        "test_account_creation.py": "integration",
        "test_broadcast_movement.py": "integration",
        
        # Unit tests (varios)
        "test_map_manager.py": "unit",
        "test_map_manager_npcs.py": "unit",
        "test_map_manager_tile_occupation.py": "unit",
        "test_npc_movement.py": "unit",
        "test_packet_reader.py": "unit",
        "test_dependency_container.py": "unit",
    }

    # Mover archivos
    print("\n📦 Moviendo tests...")
    moved_count = 0
    for test_file, category in sorted(test_mapping.items()):
        src_file = tests_dir / test_file
        if src_file.exists():
            dest_file = tests_dir / category / test_file
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {test_file} → {category}/")
            moved_count += 1

    print(f"\n✅ Reorganización completada: {moved_count} tests movidos")
    print(f"📂 Categorías creadas: {len(categories)} principales + subcategorías")


if __name__ == "__main__":
    reorganize_tests()
