"""Script para actualizar imports de models."""

from pathlib import Path

# Mapeo de imports
IMPORT_REPLACEMENTS = {
    "from src.npc import": "from src.models.npc import",
    "from src.npc_factory import": "from src.models.npc_factory import",
    "from src.item import": "from src.models.item import",
    "from src.item_types import": "from src.models.item_types import",
    "from src.item_constants import": "from src.models.item_constants import",
    "from src.items_catalog import": "from src.models.items_catalog import",
    "from src.spell_catalog import": "from src.models.spell_catalog import",
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
