"""Tests para ItemCatalog."""

from unittest.mock import mock_open, patch

from src.models.item_catalog import ItemCatalog


class TestItemCatalog:
    """Tests para ItemCatalog."""

    def test_init_default_path(self) -> None:
        """Test de inicialización con path por defecto."""
        toml_content = ""
        with (
            patch("builtins.open", mock_open(read_data=toml_content)),
            patch("tomllib.load") as mock_load,
        ):
            mock_load.return_value = {"item": {}}
            catalog = ItemCatalog()

            assert catalog is not None

    def test_get_item_data_not_found(self) -> None:
        """Test de obtención de item no existente."""
        toml_content = ""
        with (
            patch("builtins.open", mock_open(read_data=toml_content)),
            patch("tomllib.load") as mock_load,
        ):
            mock_load.return_value = {"item": {}}
            catalog = ItemCatalog()
            item_data = catalog.get_item_data(99999)

            assert item_data is None
