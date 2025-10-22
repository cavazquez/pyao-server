"""Script para actualizar imports de tasks en tests."""

from pathlib import Path

# Mapeo de imports antiguos a nuevos
IMPORT_REPLACEMENTS = {
    "from src.task_login import": "from src.tasks.player.task_login import",
    "from src.task_attack import": "from src.tasks.player.task_attack import",
    "from src.task_walk import": "from src.tasks.player.task_walk import",
    "from src.task_change_heading import": "from src.tasks.player.task_change_heading import",
    "from src.task_meditate import": "from src.tasks.player.task_meditate import",
    "from src.task_inventory_click import": "from src.tasks.inventory.task_inventory_click import",
    "from src.task_equip_item import": "from src.tasks.inventory.task_equip_item import",
    "from src.task_drop import": "from src.tasks.inventory.task_drop import",
    "from src.task_double_click import": "from src.tasks.inventory.task_double_click import",
    "from src.task_commerce_buy import": "from src.tasks.commerce.task_commerce_buy import",
    "from src.task_commerce_sell import": "from src.tasks.commerce.task_commerce_sell import",
    "from src.task_commerce_end import": "from src.tasks.commerce.task_commerce_end import",
    "from src.task_bank_deposit import": "from src.tasks.banking.task_bank_deposit import",
    "from src.task_bank_extract import": "from src.tasks.banking.task_bank_extract import",
    "from src.task_cast_spell import": "from src.tasks.spells.task_cast_spell import",
    "from src.task_left_click import": "from src.tasks.interaction.task_left_click import",
    "from src.task_information import": "from src.tasks.interaction.task_information import",
    "from src.task_work import": "from src.tasks.work.task_work import",
    "from src.task_work_left_click import": "from src.tasks.work.task_work_left_click import",
    "from src.task_gm_commands import": "from src.tasks.admin.task_gm_commands import",
}


def update_test_imports() -> None:
    """Actualiza imports en archivos de tests."""
    tests_dir = Path("tests")
    updated_count = 0
    files_updated = []

    for test_file in tests_dir.glob("*.py"):
        content = test_file.read_text()
        original_content = content

        # Aplicar reemplazos
        for old_import, new_import in IMPORT_REPLACEMENTS.items():
            content = content.replace(old_import, new_import)

        # Guardar si hubo cambios
        if content != original_content:
            test_file.write_text(content)
            updated_count += 1
            files_updated.append(test_file.name)
            print(f"✓ {test_file.name}")

    print(f"\n✅ {updated_count} archivos de tests actualizados")
    if files_updated:
        print(f"Archivos modificados: {', '.join(files_updated[:10])}")
        if len(files_updated) > 10:
            print(f"... y {len(files_updated) - 10} más")


if __name__ == "__main__":
    update_test_imports()
