"""Script para reorganizar tests restantes (Fase 7b)."""

import subprocess
from pathlib import Path


def reorganize_remaining_tests() -> None:
    """Reorganiza tests restantes en tests/."""
    tests_dir = Path("tests")
    
    print("📁 Creando estructura de tests restantes...")
    
    # Crear categorías adicionales
    categories = {
        "network": "Tests de red y protocolos",
        "effects": "Tests de efectos",
        "game": "Tests de mecánicas de juego",
        "utils": "Tests de utilidades",
        "core": "Tests de inicializadores",
    }
    
    for category, description in categories.items():
        category_dir = tests_dir / category
        if not category_dir.exists():
            category_dir.mkdir(exist_ok=True)
            (category_dir / "__init__.py").write_text(f'"""{description}."""\n')
            print(f"  ✓ tests/{category}/")
    
    # Mapeo de tests a categorías
    test_mapping = {
        # network/ - Tests de red y protocolos
        "test_client_connection.py": "network",
        "test_session_manager.py": "network",
        "test_packet_builder.py": "network",
        "test_packet_validator.py": "network",
        "test_packet_validator_complete.py": "network",
        "test_packet_validator_extended.py": "network",
        "test_msg_audio.py": "network",
        "test_msg_character.py": "network",
        "test_msg_console.py": "network",
        "test_msg_inventory.py": "network",
        "test_msg_map.py": "network",
        "test_msg_player_stats.py": "network",
        "test_msg_session.py": "network",
        "test_msg_visual_effects.py": "network",
        
        # effects/ - Tests de efectos
        "test_effect_gold_decay.py": "effects",
        "test_effect_hunger_thirst.py": "effects",
        "test_meditation_effect.py": "effects",
        "test_npc_ai_effect.py": "effects",
        "test_tick_effect.py": "effects",
        
        # game/ - Tests de mecánicas
        "test_game_tick.py": "game",
        "test_game_tick_initializer.py": "game",
        "test_map_manager_exit_tiles.py": "game",
        
        # utils/ - Tests de utilidades
        "test_password_utils.py": "utils",
        "test_inventory_slot.py": "utils",
        "test_inventory_stacking_strategy.py": "utils",
        "test_inventory_storage.py": "utils",
        "test_sounds.py": "utils",
        "test_visual_effects.py": "utils",
        "test_redis_client.py": "utils",
        
        # core/ - Tests de inicializadores
        "test_data_initializer.py": "core",
        "test_repository_initializer.py": "core",
        
        # models/ - Adicionales
        "test_item_catalog.py": "models",
        "test_npc_catalog.py": "models",
        "test_merchant_data_loader.py": "models",
        
        # tasks/ - Tasks misc restantes
        "test_task_ayuda.py": "tasks",
        "test_task_dice.py": "tasks",
        "test_task_motd.py": "tasks",
        "test_task_null.py": "tasks",
        "test_task_online.py": "tasks",
        "test_task_ping.py": "tasks",
        "test_task_quit.py": "tasks",
        "test_task_uptime.py": "tasks",
        
        # tasks/banking/ - Adicional
        "test_task_bank_end.py": "tasks/banking",
        
        # tasks/player/ - Adicional
        "test_task_request_stats.py": "tasks/player",
        
        # tasks/interaction/ - Adicional
        "test_task_talk.py": "tasks/interaction",
        
        # unit/ - Tests varios
        "test_music.py": "unit",
        "test_server_cli.py": "unit",
    }
    
    # Archivos que quedan en raíz
    keep_in_root = {
        "conftest.py",  # Configuración de pytest
        "__init__.py",  # Package marker
        "test_init.py",  # Test del __init__
    }
    
    # Mover archivos
    print("\n📦 Moviendo tests...")
    moved_count = 0
    
    for test_file, category in sorted(test_mapping.items()):
        src_file = tests_dir / test_file
        if src_file.exists():
            dest_file = tests_dir / category / test_file
            # Crear subcarpetas si es necesario
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if not (dest_file.parent / "__init__.py").exists():
                (dest_file.parent / "__init__.py").write_text(f'"""Tests de {dest_file.parent.name}."""\n')
            
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {test_file} → {category}/")
            moved_count += 1
    
    print(f"\n✅ Reorganización completada: {moved_count} tests movidos")
    print(f"\nArchivos en raíz de tests/: {len(keep_in_root)}")


if __name__ == "__main__":
    reorganize_remaining_tests()
