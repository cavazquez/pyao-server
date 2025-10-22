"""Script para actualizar imports de repositories."""

from pathlib import Path

# Mapeo de imports
IMPORT_REPLACEMENTS = {
    "from src.account_repository import": "from src.repositories.account_repository import",
    "from src.bank_repository import": "from src.repositories.bank_repository import",
    "from src.equipment_repository import": "from src.repositories.equipment_repository import",
    "from src.ground_items_repository import": "from src.repositories.ground_items_repository import",
    "from src.inventory_repository import": "from src.repositories.inventory_repository import",
    "from src.merchant_repository import": "from src.repositories.merchant_repository import",
    "from src.npc_repository import": "from src.repositories.npc_repository import",
    "from src.player_repository import": "from src.repositories.player_repository import",
    "from src.server_repository import": "from src.repositories.server_repository import",
    "from src.spellbook_repository import": "from src.repositories.spellbook_repository import",
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
