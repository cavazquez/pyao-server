"""Diagnóstico de tala sobre las regresiones aisladas del flujo vigente.

El diagnóstico antiguo construía una TaskWorkLeftClick con dependencias que ya
no admite y simulaba add_item en vez del commit atómico. Este punto de entrada
conserva el comando manual, ejecutando parsing/delegación y recolección real
sobre Redis falso, con éxito, fallo, rechazos y replay sin duplicar recursos.
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Ejecuta las regresiones equivalentes y devuelve su resultado."""
    root = Path(__file__).resolve().parent
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/tasks/work/test_task_work_left_click.py",
            "tests/services/test_gameplay_skills.py",
            "-k",
            "TestTaskWorkLeftClick or gathering",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
