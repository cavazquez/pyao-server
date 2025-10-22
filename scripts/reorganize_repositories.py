"""Script para reorganizar repositories."""

import subprocess
from pathlib import Path


def reorganize_repositories() -> None:
    """Reorganiza repositories en subcarpeta."""
    src_dir = Path("src")
    repos_dir = src_dir / "repositories"

    # Crear estructura
    print("📁 Creando estructura de repositories...")
    repos_dir.mkdir(exist_ok=True)
    (repos_dir / "__init__.py").write_text('"""Package de repositories (capa de datos)."""\n')
    print("  ✓ repositories/")

    # Repositorios a mover
    repositories = [
        "account_repository.py",
        "bank_repository.py",
        "equipment_repository.py",
        "ground_items_repository.py",
        "inventory_repository.py",
        "merchant_repository.py",
        "npc_repository.py",
        "player_repository.py",
        "server_repository.py",
        "spellbook_repository.py",
    ]

    # Mover archivos
    print("\n📦 Moviendo repositories...")
    moved_count = 0
    for repo in repositories:
        src_file = src_dir / repo
        if src_file.exists():
            dest_file = repos_dir / repo
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {repo}")
            moved_count += 1

    print(f"\n✅ Reorganización completada: {moved_count} archivos movidos")
    print("\n⚠️  SIGUIENTE PASO: Actualizar imports")


if __name__ == "__main__":
    reorganize_repositories()
