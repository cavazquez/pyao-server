"""Genera una credencial Redis local sin mostrarla ni sobrescribir otra existente."""

import argparse
import os
from pathlib import Path
from secrets import token_urlsafe


def create_secret(path: Path) -> None:
    """Escribe un secreto aleatorio con permisos 0600 y creación exclusiva."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as target:
        target.write(token_urlsafe(32) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    create_secret(parser.parse_args().output)
    print("Secreto Redis creado con permisos 0600; su contenido no se imprime")
