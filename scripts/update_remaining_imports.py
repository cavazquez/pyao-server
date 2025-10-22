"""Script para actualizar imports de archivos reorganizados (Fase 7)."""

from pathlib import Path

# Mapeo masivo de imports
IMPORT_REPLACEMENTS = {
    # network/
    "from src.packet_builder import": "from src.network.packet_builder import",
    "from src.packet_data import": "from src.network.packet_data import",
    "from src.packet_handlers import": "from src.network.packet_handlers import",
    "from src.packet_id import": "from src.network.packet_id import",
    "from src.packet_reader import": "from src.network.packet_reader import",
    "from src.packet_validator import": "from src.network.packet_validator import",
    "from src.client_connection import": "from src.network.client_connection import",
    "from src.session_manager import": "from src.network.session_manager import",
    
    # network/ - msg builders
    "from src.msg_audio import": "from src.network.msg_audio import",
    "from src.msg_character import": "from src.network.msg_character import",
    "from src.msg_console import": "from src.network.msg_console import",
    "from src.msg_inventory import": "from src.network.msg_inventory import",
    "from src.msg_map import": "from src.network.msg_map import",
    "from src.msg_player_stats import": "from src.network.msg_player_stats import",
    "from src.msg_session import": "from src.network.msg_session import",
    "from src.msg_visual_effects import": "from src.network.msg_visual_effects import",
    
    # core/
    "from src.dependency_container import": "from src.core.dependency_container import",
    "from src.data_initializer import": "from src.core.data_initializer import",
    "from src.game_tick_initializer import": "from src.core.game_tick_initializer import",
    "from src.redis_initializer import": "from src.core.redis_initializer import",
    "from src.repository_initializer import": "from src.core.repository_initializer import",
    "from src.server_initializer import": "from src.core.server_initializer import",
    "from src.service_initializer import": "from src.core.service_initializer import",
    
    # combat/
    "from src.combat_critical_calculator import": "from src.combat.combat_critical_calculator import",
    "from src.combat_damage_calculator import": "from src.combat.combat_damage_calculator import",
    "from src.combat_reward_calculator import": "from src.combat.combat_reward_calculator import",
    "from src.combat_validator import": "from src.combat.combat_validator import",
    
    # effects/
    "from src.effect_gold_decay import": "from src.effects.effect_gold_decay import",
    "from src.effect_hunger_thirst import": "from src.effects.effect_hunger_thirst import",
    "from src.effect_npc_movement import": "from src.effects.effect_npc_movement import",
    "from src.effect_stamina_regen import": "from src.effects.effect_stamina_regen import",
    "from src.meditation_effect import": "from src.effects.meditation_effect import",
    "from src.npc_ai_effect import": "from src.effects.npc_ai_effect import",
    "from src.tick_effect import": "from src.effects.tick_effect import",
    
    # game/
    "from src.game_tick import": "from src.game.game_tick import",
    "from src.map_manager import": "from src.game.map_manager import",
    "from src.map_manager_spatial import": "from src.game.map_manager_spatial import",
    
    # utils/
    "from src.password_utils import": "from src.utils.password_utils import",
    "from src.equipment_slot import": "from src.utils.equipment_slot import",
    "from src.inventory_slot import": "from src.utils.inventory_slot import",
    "from src.inventory_stacking_strategy import": "from src.utils.inventory_stacking_strategy import",
    "from src.inventory_storage import": "from src.utils.inventory_storage import",
    "from src.sounds import": "from src.utils.sounds import",
    "from src.visual_effects import": "from src.utils.visual_effects import",
    "from src.base_data_loader import": "from src.utils.base_data_loader import",
    "from src.redis_client import": "from src.utils.redis_client import",
    "from src.redis_config import": "from src.utils.redis_config import",
    
    # tasks/ - base y factory
    "from src.task import": "from src.tasks.task import",
    "from src.task_factory import": "from src.tasks.task_factory import",
    
    # tasks/player - adicionales
    "from src.task_account import": "from src.tasks.player.task_account import",
    "from src.task_attributes import": "from src.tasks.player.task_attributes import",
    "from src.task_request_stats import": "from src.tasks.player.task_request_stats import",
    "from src.task_request_position_update import": "from src.tasks.player.task_request_position_update import",
    
    # tasks/banking - adicionales
    "from src.task_bank_deposit_gold import": "from src.tasks.banking.task_bank_deposit_gold import",
    "from src.task_bank_extract_gold import": "from src.tasks.banking.task_bank_extract_gold import",
    "from src.task_bank_end import": "from src.tasks.banking.task_bank_end import",
    
    # tasks/interaction - adicionales
    "from src.task_pickup import": "from src.tasks.interaction.task_pickup import",
    "from src.task_talk import": "from src.tasks.interaction.task_talk import",
    
    # tasks/ misc
    "from src.task_ayuda import": "from src.tasks.task_ayuda import",
    "from src.task_dice import": "from src.tasks.task_dice import",
    "from src.task_motd import": "from src.tasks.task_motd import",
    "from src.task_null import": "from src.tasks.task_null import",
    "from src.task_online import": "from src.tasks.task_online import",
    "from src.task_ping import": "from src.tasks.task_ping import",
    "from src.task_quit import": "from src.tasks.task_quit import",
    "from src.task_uptime import": "from src.tasks.task_uptime import",
    
    # models - adicionales
    "from src.item_catalog import": "from src.models.item_catalog import",
    "from src.npc_catalog import": "from src.models.npc_catalog import",
    "from src.merchant_data_loader import": "from src.models.merchant_data_loader import",
}


def update_imports_in_file(file_path: Path) -> bool:
    """Actualiza imports en un archivo."""
    try:
        content = file_path.read_text()
        original_content = content

        for old_import, new_import in IMPORT_REPLACEMENTS.items():
            content = content.replace(old_import, new_import)

        if content != original_content:
            file_path.write_text(content)
            return True
        return False
    except Exception as e:
        print(f"  ⚠️  Error en {file_path}: {e}")
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
    for py_file in Path("tests").rglob("*.py"):
        if update_imports_in_file(py_file):
            updated_count += 1
            print(f"  ✓ {py_file.relative_to('tests')}")
    
    print(f"\n✅ {updated_count} archivos actualizados")


if __name__ == "__main__":
    update_all_imports()
