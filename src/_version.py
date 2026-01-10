"""Módulo para obtener la versión del paquete."""

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("src")
except PackageNotFoundError:
    # Fallback: leer desde pyproject.toml si no está instalado
    import tomllib
    from pathlib import Path

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    __version__ = pyproject["project"]["version"]
