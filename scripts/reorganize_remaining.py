"""Script para reorganizar archivos restantes (Fase 7 - Final)."""

import subprocess
from pathlib import Path


def reorganize_remaining() -> None:
    """Reorganiza archivos restantes en src/."""
    src_dir = Path("src")
    
    print("📁 Creando estructura final...")
    
    # Crear categorías
    categories = {
        "network": "Capa de red y protocolo",
        "core": "Core del servidor",
        "combat": "Sistema de combate",
        "effects": "Efectos del juego",
        "utils": "Utilidades",
        "game": "Mecánicas de juego",
    }
    
    for category, description in categories.items():
        category_dir = src_dir / category
        category_dir.mkdir(exist_ok=True)
        (category_dir / "__init__.py").write_text(f'"""{description}."""\n')
        print(f"  ✓ {category}/")
    
    # Mapeo de archivos
    file_mapping = {
        # network/ - Protocolos y packets
        "packet_builder.py": "network",
        "packet_data.py": "network",
        "packet_handlers.py": "network",
        "packet_id.py": "network",
        "packet_reader.py": "network",
        "packet_validator.py": "network",
        "client_connection.py": "network",
        "session_manager.py": "network",
        
        # network/messages/ - Builders de mensajes (msg_*.py)
        "msg_audio.py": "network",
        "msg_character.py": "network",
        "msg_console.py": "network",
        "msg_inventory.py": "network",
        "msg_map.py": "network",
        "msg_player_stats.py": "network",
        "msg_session.py": "network",
        "msg_visual_effects.py": "network",
        
        # core/ - Inicialización y configuración
        "dependency_container.py": "core",
        "data_initializer.py": "core",
        "game_tick_initializer.py": "core",
        "redis_initializer.py": "core",
        "repository_initializer.py": "core",
        "server_initializer.py": "core",
        "service_initializer.py": "core",
        
        # combat/ - Calculadoras y validadores de combate
        "combat_critical_calculator.py": "combat",
        "combat_damage_calculator.py": "combat",
        "combat_reward_calculator.py": "combat",
        "combat_validator.py": "combat",
        
        # effects/ - Efectos del juego
        "effect_gold_decay.py": "effects",
        "effect_hunger_thirst.py": "effects",
        "effect_npc_movement.py": "effects",
        "effect_stamina_regen.py": "effects",
        "meditation_effect.py": "effects",
        "npc_ai_effect.py": "effects",
        "tick_effect.py": "effects",
        
        # game/ - Mecánicas de juego
        "game_tick.py": "game",
        "map_manager.py": "game",
        "map_manager_spatial.py": "game",
        
        # utils/ - Utilidades
        "password_utils.py": "utils",
        "equipment_slot.py": "utils",
        "inventory_slot.py": "utils",
        "inventory_stacking_strategy.py": "utils",
        "inventory_storage.py": "utils",
        "sounds.py": "utils",
        "visual_effects.py": "utils",
        "base_data_loader.py": "utils",
        "redis_client.py": "utils",
        "redis_config.py": "utils",
        
        # Tasks restantes que no se movieron
        "task.py": "tasks",  # Base class
        "task_factory.py": "tasks",  # Factory
        "task_account.py": "tasks/player",
        "task_attributes.py": "tasks/player",
        "task_request_stats.py": "tasks/player",
        "task_bank_deposit_gold.py": "tasks/banking",
        "task_bank_extract_gold.py": "tasks/banking",
        "task_bank_end.py": "tasks/banking",
        "task_pickup.py": "tasks/interaction",
        "task_talk.py": "tasks/interaction",
        "task_request_position_update.py": "tasks/player",
        
        # Tasks misc (pueden ir a unit)
        "task_ayuda.py": "tasks",
        "task_dice.py": "tasks",
        "task_motd.py": "tasks",
        "task_null.py": "tasks",
        "task_online.py": "tasks",
        "task_ping.py": "tasks",
        "task_quit.py": "tasks",
        "task_uptime.py": "tasks",
        
        # Data loaders
        "item_catalog.py": "models",
        "npc_catalog.py": "models",
        "merchant_data_loader.py": "models",
    }
    
    # Archivos que deben quedarse en src/ (entry points y core)
    keep_in_root = {
        "server.py",  # Entry point principal
        "run_server.py",  # Script de ejecución
        "server_cli.py",  # CLI
        "__init__.py",  # Package marker
    }
    
    # Mover archivos
    print("\n📦 Moviendo archivos...")
    moved_count = 0
    
    for file, category in sorted(file_mapping.items()):
        src_file = src_dir / file
        if src_file.exists():
            dest_file = src_dir / category / file
            # Crear subcarpetas si es necesario (tasks/player, etc.)
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            if not (dest_file.parent / "__init__.py").exists():
                (dest_file.parent / "__init__.py").write_text(f'"""Módulo {dest_file.parent.name}."""\n')
            
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {file} → {category}/")
            moved_count += 1
    
    print(f"\n✅ Reorganización completada: {moved_count} archivos movidos")
    print(f"\nArchivos en raíz de src/ (core): {len(keep_in_root)}")
    print("\n⚠️  SIGUIENTE PASO: Actualizar imports")


if __name__ == "__main__":
    reorganize_remaining()
