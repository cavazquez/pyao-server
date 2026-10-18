"""Recursos del paquete y estado del operador independientes del directorio actual."""

from src import runtime_paths
from src.models.item_catalog import ItemCatalog
from src.models.spell_catalog import SpellCatalog


def test_catalogs_from_another_working_directory(tmp_path, monkeypatch) -> None:
    """Cambiar cwd no reemplaza el dataset versionado por un directorio vacío."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PYAO_DATA_DIR", raising=False)
    monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
    assert ItemCatalog().get_item_data(862) is not None
    assert SpellCatalog().get_spell_data(2) is not None
    assert runtime_paths.data_dir().is_absolute()


def test_operator_paths_and_editable_config_precede_package(tmp_path, monkeypatch) -> None:
    """Los overrides del operador no escriben ni reemplazan los recursos incluidos."""
    state = tmp_path / "state"
    config = state / "config/server.toml"
    config.parent.mkdir(parents=True)
    config.write_text("[server]\nport=8888\n")
    monkeypatch.setenv("PYAO_STATE_DIR", str(state))
    monkeypatch.setenv("PYAO_DATA_DIR", str(tmp_path / "custom-data"))
    monkeypatch.setenv("PYAO_MAPS_DIR", str(tmp_path / "custom-maps"))
    assert runtime_paths.config_file() == config
    assert runtime_paths.data_dir() == tmp_path / "custom-data"
    assert runtime_paths.maps_dir() == tmp_path / "custom-maps"
    explicit = tmp_path / "alternate.toml"
    monkeypatch.setenv("PYAO_CONFIG_FILE", str(explicit))
    assert runtime_paths.config_file() == explicit


def test_installed_maps_are_extracted_only_under_operator_state(tmp_path, monkeypatch) -> None:
    """El archive real se extrae en caché por hash y se reutiliza sin alterar el paquete."""
    package = tmp_path / "package"
    (package / "archives").mkdir(parents=True)
    archive = package / "archives/map_data.xz"
    archive.write_bytes((runtime_paths.SOURCE_ROOT / "archives/map_data.xz").read_bytes())
    monkeypatch.setattr(runtime_paths, "BUNDLED_ROOT", package)
    monkeypatch.setenv("PYAO_STATE_DIR", str(tmp_path / "operator"))
    monkeypatch.delenv("PYAO_MAPS_DIR", raising=False)
    maps = runtime_paths.maps_dir()
    assert maps.is_relative_to(tmp_path / "operator")
    assert (maps / "metadata_001-051.json").is_file()
    stamp = (maps / "metadata_001-051.json").stat().st_mtime_ns
    assert runtime_paths.maps_dir() == maps
    assert (maps / "metadata_001-051.json").stat().st_mtime_ns == stamp
    assert sorted(path.name for path in package.iterdir()) == ["archives"]
