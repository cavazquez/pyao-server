"""Tests para __init__.py."""

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
