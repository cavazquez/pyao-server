"""Rutas del catálogo de carteles independientes del cwd y con precedencia Snap."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.command_handlers.left_click_tile_handler import LeftClickTileHandler, load_signs_catalog


@pytest.mark.parametrize("other_cwd", [False, True])
def test_bundled_catalog_is_independent_of_cwd(tmp_path, monkeypatch, other_cwd: bool) -> None:
    """El catálogo incluido conserva el texto conocido de GrhIndex=500."""
    monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
    if other_cwd:
        monkeypatch.chdir(tmp_path)
    catalog = load_signs_catalog()
    assert catalog[500]["text"] == "Tenemos las mejores armas para los mejores guerreros."


def test_snap_common_precedes_explicit_data_root(tmp_path, monkeypatch) -> None:
    """Un catálogo del operador en SNAP_USER_COMMON no es reemplazado por el incluido."""
    monkeypatch.setenv("SNAP_USER_COMMON", str(tmp_path))
    target = tmp_path / "data/items/world_objects/signs.toml"
    target.parent.mkdir(parents=True)
    target.write_text('[[item]]\nGrhIndex=500\nTexto="Cartel de instancia"\n')
    assert load_signs_catalog(Path("/does-not-exist"))[500]["text"] == "Cartel de instancia"


def test_missing_catalog_reports_effective_path(tmp_path, monkeypatch, caplog) -> None:
    """El archivo ausente se diagnostica sin un traceback ni dependencia del cwd."""
    monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
    assert load_signs_catalog(tmp_path) == {}
    assert str(tmp_path / "items/world_objects/signs.toml") in caplog.text


@pytest.mark.asyncio
async def test_known_sign_is_returned_by_interaction(monkeypatch) -> None:
    """La interacción de mapa devuelve el texto del catálogo efectivo."""
    monkeypatch.delenv("SNAP_USER_COMMON", raising=False)
    resources = MagicMock(get_sign_at=MagicMock(return_value=500))
    handler = LeftClickTileHandler(
        map_manager=None,
        map_resources=resources,
        door_service=None,
        door_repo=None,
        message_sender=MagicMock(send_console_msg=AsyncMock()),
    )
    with patch(
        "src.command_handlers.left_click_tile_handler._SIGNS_CATALOG", load_signs_catalog()
    ):
        assert (
            await handler._get_sign_text(1, 50, 50)
            == "Tenemos las mejores armas para los mejores guerreros."
        )
