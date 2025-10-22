"""Script para reorganizar tasks en subcarpetas por categoría."""

import subprocess
from pathlib import Path

# Mapeo de archivos a carpetas
TASK_MAPPING = {
    # player/
    "task_login.py": "player",
    "task_create_account.py": "player",
    "task_walk.py": "player",
    "task_change_heading.py": "player",
    "task_attack.py": "player",
    "task_meditate.py": "player",
    "task_safe_toggle.py": "player",
    "task_request_pos_update.py": "player",
    # inventory/
    "task_inventory_click.py": "inventory",
    "task_equip_item.py": "inventory",
    "task_drop.py": "inventory",
    "task_double_click.py": "inventory",
    # commerce/
    "task_commerce_buy.py": "commerce",
    "task_commerce_sell.py": "commerce",
    "task_commerce_end.py": "commerce",
    # banking/
    "task_bank_deposit.py": "banking",
    "task_bank_extract.py": "banking",
    # spells/
    "task_cast_spell.py": "spells",
    "task_spell_info.py": "spells",
    "task_move_spell.py": "spells",
    # interaction/
    "task_left_click.py": "interaction",
    "task_information.py": "interaction",
    # work/
    "task_work.py": "work",
    "task_work_left_click.py": "work",
    # admin/
    "task_gm_commands.py": "admin",
}


def reorganize_tasks() -> None:
    """Reorganiza tasks en subcarpetas."""
    src_dir = Path("src")
    tasks_dir = src_dir / "tasks"

    # Crear estructura de carpetas
    print("📁 Creando estructura de carpetas...")
    categories = sorted(set(TASK_MAPPING.values()))
    for category in categories:
        category_dir = tasks_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        (category_dir / "__init__.py").touch()
        print(f"  ✓ tasks/{category}/")

    # Crear __init__.py principal
    (tasks_dir / "__init__.py").write_text('"""Package de tasks del servidor."""\n')

    # Mover archivos usando git mv para preservar historia
    print("\n📦 Moviendo archivos...")
    moved_count = 0
    for file, category in sorted(TASK_MAPPING.items()):
        src_file = src_dir / file
        if src_file.exists():
            dest_file = tasks_dir / category / file
            # Usar git mv para preservar historia
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {file} → tasks/{category}/")
            moved_count += 1
        else:
            print(f"  ⚠️  {file} no encontrado")

    print(f"\n✅ Reorganización completada: {moved_count} archivos movidos")
    print(f"📂 Categorías creadas: {len(categories)}")
    print("\n⚠️  SIGUIENTE PASO: Actualizar imports en:")
    print("  - src/packet_handlers.py")
    print("  - src/task_factory.py")
    print("  - tests/*")


if __name__ == "__main__":
    reorganize_tasks()
