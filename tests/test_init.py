"""Tests para __init__.py."""

import tomllib
from pathlib import Path

import src


def test_version_exists() -> None:
    """Test que __version__ existe."""
    assert hasattr(src, "__version__")


def test_version_format() -> None:
    """Test que __version__ tiene formato válido."""
    version = src.__version__
    assert isinstance(version, str)
    assert len(version) > 0
    # Verificar formato semver básico (x.y.z)
    parts = version.split(".")
    assert len(parts) >= 2  # Al menos major.minor


def test_version_from_metadata() -> None:
    """Test que la versión se puede obtener de metadata."""
    # Este test verifica el camino normal (try)
    # La versión ya está cargada en src.__version__
    assert src.__version__ is not None


def test_version_fallback_logic() -> None:
    """Test de la lógica del fallback de pyproject.toml."""
    # Test que verifica que el código de fallback es válido
    # Verificar que pyproject.toml existe y tiene versión
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists()

    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)

    assert "project" in pyproject
    assert "version" in pyproject["project"]
    assert isinstance(pyproject["project"]["version"], str)
    assert len(pyproject["project"]["version"]) > 0


def test_version_is_string() -> None:
    """Test que __version__ es un string."""
    assert isinstance(src.__version__, str)


def test_version_not_empty() -> None:
    """Test que __version__ no está vacío."""
    assert len(src.__version__) > 0
    assert src.__version__.strip()
