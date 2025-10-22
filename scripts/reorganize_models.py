"""Script para reorganizar models y catalogs."""

import subprocess
from pathlib import Path


def reorganize_models() -> None:
    """Reorganiza models en subcarpetas."""
    src_dir = Path("src")
    models_dir = src_dir / "models"

    # Crear estructura
    print("📁 Creando estructura de models...")
    models_dir.mkdir(exist_ok=True)
    (models_dir / "__init__.py").write_text('"""Package de models (modelos de datos)."""\n')
    print("  ✓ models/")

    # Archivos a mover (modelos de datos y sus catálogos)
    models = [
        "player.py",
        "npc.py",
        "npc_factory.py",
        "item.py",
        "item_types.py",
        "item_constants.py",
        "items_catalog.py",
        "spell.py",
        "spell_catalog.py",
        "ground_item.py",
        "position.py",
        "heading.py",
    ]

    # Mover archivos
    print("\n📦 Moviendo models...")
    moved_count = 0
    for model in models:
        src_file = src_dir / model
        if src_file.exists():
            dest_file = models_dir / model
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {model}")
            moved_count += 1
        else:
            print(f"  ⚠️  {model} no encontrado")

    print(f"\n✅ Reorganización completada: {moved_count} archivos movidos")
    print("\n⚠️  SIGUIENTE PASO: Actualizar imports")


if __name__ == "__main__":
    reorganize_models()
