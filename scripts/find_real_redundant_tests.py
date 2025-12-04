#!/usr/bin/env python3
"""Script para identificar tests realmente redundantes eliminándolos uno por uno."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

REDUNDANT_TEST_FILES = [
    "tests/test_init.py",
    "tests/effects/test_tick_effect.py",
    "tests/combat/test_combat_reward_calculator.py",
    "tests/unit/test_dependency_container.py",
    "tests/network/test_msg_visual_effects.py",
    "tests/network/test_msg_audio.py",
    "tests/network/test_msg_console.py",
    "tests/network/test_msg_map.py",
    "tests/network/test_msg_character.py",
    "tests/services/npc/test_npc_sounds.py",
    "tests/network/test_msg_player_stats.py",
    "tests/messaging/test_message_console_sender.py",
    "tests/models/test_character_class.py",
    "tests/unit/test_config.py",
    "tests/models/test_item_types.py",
    "tests/tasks/admin/test_task_gm_commands.py",
    "tests/integration/test_broadcast_movement.py",
    "tests/services/npc/test_npc_ai_configurable.py",
    "tests/integration/test_class_system_integration.py",
    "tests/services/player/test_player_service.py",
]


def get_coverage_lines(base_dir: Path) -> int:
    """Obtiene el número de líneas cubiertas."""
    subprocess.run(
        ["rm", "-f", ".coverage", "coverage.json"],
        cwd=base_dir,
        capture_output=True,
    )

    result = subprocess.run(
        ["uv", "run", "pytest", "--cov=src", "--cov-report=json", "-q"],
        cwd=base_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return -1

    coverage_file = base_dir / "coverage.json"
    if not coverage_file.exists():
        return -1

    try:
        with open(coverage_file) as f:
            coverage_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return -1

    return coverage_data.get("totals", {}).get("covered_lines", 0)


def test_remove_single_file(base_dir: Path, test_file: str) -> tuple[bool, int]:
    """Prueba eliminar un solo archivo y retorna si afectó la cobertura."""
    file_path = base_dir / test_file
    if not file_path.exists():
        return False, 0

    # Obtener cobertura inicial
    coverage_before = get_coverage_lines(base_dir)
    if coverage_before == -1:
        return False, 0

    # Eliminar archivo
    backup_path = base_dir / f"{test_file}.backup"
    file_path.rename(backup_path)

    # Obtener cobertura después
    coverage_after = get_coverage_lines(base_dir)

    # Restaurar archivo
    backup_path.rename(file_path)

    if coverage_after == -1:
        return False, 0

    diff = coverage_after - coverage_before
    return diff == 0, diff


def main() -> None:
    """Función principal."""
    base_dir = Path(__file__).parent.parent

    print("=" * 70)
    print("🔍 Identificando Tests Realmente Redundantes")
    print("=" * 70)
    print()

    really_redundant = []
    not_redundant = []

    for i, test_file in enumerate(REDUNDANT_TEST_FILES, 1):
        print(f"[{i}/{len(REDUNDANT_TEST_FILES)}] Probando {test_file}...", end=" ", flush=True)
        is_redundant, diff = test_remove_single_file(base_dir, test_file)

        if is_redundant:
            really_redundant.append((test_file, diff))
            print(f"✅ Redundante (diferencia: {diff:+d})")
        else:
            not_redundant.append((test_file, diff))
            print(f"⚠️  NO redundante (diferencia: {diff:+d})")

    print()
    print("=" * 70)
    print("📊 Resultados")
    print("=" * 70)
    print()
    print(f"✅ Tests realmente redundantes: {len(really_redundant)}")
    for test_file, diff in really_redundant:
        print(f"   - {test_file} (diferencia: {diff:+d})")

    print()
    print(f"⚠️  Tests que NO son redundantes: {len(not_redundant)}")
    for test_file, diff in not_redundant:
        print(f"   - {test_file} (diferencia: {diff:+d})")


if __name__ == "__main__":
    main()




