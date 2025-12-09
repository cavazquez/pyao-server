"""Tests adicionales para MapManager para mejorar cobertura."""

import json
import tempfile
from pathlib import Path

import pytest

from src.game.map_manager import MapManager
from src.game.map_metadata_loader import MapMetadataLoader


@pytest.fixture
def map_manager() -> MapManager:
    """Fixture que crea un MapManager."""
    return MapManager()


class TestMapManagerLoadTransitions:
    """Tests para carga de transiciones de mapas."""

    def test_load_map_transitions_json_format(self, map_manager: MapManager) -> None:
        """Test carga transiciones desde JSON tradicional."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transitions_path = Path(tmpdir) / "transitions_001-050.json"
            transitions_data = {
                "transitions": [
                    {
                        "from_map": 1,
                        "exits": [
                            {"x": 50, "y": 1, "to_map": 2, "to_x": 50, "to_y": 99},
                            {"x": 1, "y": 50, "to_map": 3, "to_x": 99, "to_y": 50},
                        ],
                    }
                ]
            }
            with transitions_path.open("w", encoding="utf-8") as f:
                json.dump(transitions_data, f)

            loader = map_manager._metadata_loader
            exit_tiles = map_manager._exit_tiles
            loader.load_map_transitions(1, transitions_path, exit_tiles)

            # Verificar que se cargaron las transiciones
            exit_1 = map_manager.get_exit_tile(1, 50, 1)
            assert exit_1 is not None
            assert exit_1["to_map"] == 2
            assert exit_1["to_x"] == 50
            assert exit_1["to_y"] == 99

            exit_2 = map_manager.get_exit_tile(1, 1, 50)
            assert exit_2 is not None
            assert exit_2["to_map"] == 3

    def test_load_map_transitions_list_format(self, map_manager: MapManager) -> None:
        """Test carga transiciones desde formato lista."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transitions_path = Path(tmpdir) / "transitions_001-050.json"
            # Formato lista: lista de grupos de transiciones
            transitions_data = [
                {
                    "from_map": 1,
                    "exits": [
                        {"x": 50, "y": 1, "to_map": 2, "to_x": 50, "to_y": 99},
                    ],
                }
            ]
            with transitions_path.open("w", encoding="utf-8") as f:
                json.dump(transitions_data, f)

            loader = map_manager._metadata_loader
            exit_tiles = map_manager._exit_tiles
            loader.load_map_transitions(1, transitions_path, exit_tiles)

            # Verificar que se cargó la transición
            exit_tile = map_manager.get_exit_tile(1, 50, 1)
            assert exit_tile is not None
            assert exit_tile["to_map"] == 2

    def test_load_map_transitions_nonexistent_file(self, map_manager: MapManager) -> None:
        """Test carga transiciones con archivo inexistente."""
        nonexistent_path = Path("/nonexistent/transitions.json")
        loader = map_manager._metadata_loader
        exit_tiles = map_manager._exit_tiles
        loader.load_map_transitions(1, nonexistent_path, exit_tiles)

        # No debe crashear, solo registrar en _missing_transitions_files
        assert nonexistent_path in map_manager._metadata_loader.missing_transitions_files

    def test_load_map_transitions_invalid_json(self, map_manager: MapManager) -> None:
        """Test carga transiciones con JSON inválido."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transitions_path = Path(tmpdir) / "transitions_001-050.json"
            transitions_path.write_text("invalid json {")

            loader = map_manager._metadata_loader
            exit_tiles = map_manager._exit_tiles
            loader.load_map_transitions(1, transitions_path, exit_tiles)

            # No debe crashear, debe intentar parsear como NDJSON

    def test_load_map_transitions_wrong_map_id(self, map_manager: MapManager) -> None:
        """Test carga transiciones con from_map diferente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transitions_path = Path(tmpdir) / "transitions_001-050.json"
            transitions_data = {
                "transitions": [
                    {
                        "from_map": 2,  # Diferente al map_id solicitado
                        "exits": [{"x": 50, "y": 1, "to_map": 3, "to_x": 50, "to_y": 99}],
                    }
                ]
            }
            with transitions_path.open("w", encoding="utf-8") as f:
                json.dump(transitions_data, f)

            loader = map_manager._metadata_loader
            exit_tiles = map_manager._exit_tiles
            loader.load_map_transitions(1, transitions_path, exit_tiles)

            # No debe cargar transiciones para mapa 1
            exit_tile = map_manager.get_exit_tile(1, 50, 1)
            assert exit_tile is None

    def test_load_map_transitions_invalid_coordinates(self, map_manager: MapManager) -> None:
        """Test carga transiciones con coordenadas inválidas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transitions_path = Path(tmpdir) / "transitions_001-050.json"
            transitions_data = {
                "transitions": [
                    {
                        "from_map": 1,
                        "exits": [
                            # Coordenadas fuera de rango
                            {"x": 50, "y": 1, "to_map": 999, "to_x": 50, "to_y": 99},
                            # Coordenadas válidas
                            {"x": 50, "y": 1, "to_map": 2, "to_x": 50, "to_y": 99},
                        ],
                    }
                ]
            }
            with transitions_path.open("w", encoding="utf-8") as f:
                json.dump(transitions_data, f)

            loader = map_manager._metadata_loader
            exit_tiles = map_manager._exit_tiles
            loader.load_map_transitions(1, transitions_path, exit_tiles)

            # Solo debe cargar la transición válida
            exit_tile = map_manager.get_exit_tile(1, 50, 1)
            assert exit_tile is not None
            assert exit_tile["to_map"] == 2  # La válida


class TestMapManagerBuildBlockedData:
    """Tests para _build_blocked_data."""

    def test_build_blocked_data_with_exits(self) -> None:
        """Test _build_blocked_data con tiles de exit."""
        blocked_tiles = [
            {"x": 10, "y": 20, "type": "building"},
            {"x": 50, "y": 1, "type": "exit", "to_map": 2, "to_x": 50, "to_y": 99},
            {"x": 1, "y": 50, "type": "exit", "to_map": 3, "to_x": 99, "to_y": 50},
        ]

        blocked_set, exit_count, exit_tiles = MapMetadataLoader.build_blocked_data(1, blocked_tiles)

        # Verificar tiles bloqueados
        assert (10, 20) in blocked_set
        assert (50, 1) in blocked_set  # Exit también bloquea
        assert (1, 50) in blocked_set

        # Verificar exits
        assert exit_count == 2
        assert (1, 50, 1) in exit_tiles
        assert (1, 1, 50) in exit_tiles
        assert exit_tiles[1, 50, 1]["to_map"] == 2
        assert exit_tiles[1, 1, 50]["to_map"] == 3

    def test_build_blocked_data_no_exits(self) -> None:
        """Test _build_blocked_data sin tiles de exit."""
        blocked_tiles = [
            {"x": 10, "y": 20, "type": "building"},
            {"x": 15, "y": 25, "type": "wall"},
        ]

        blocked_set, exit_count, exit_tiles = MapMetadataLoader.build_blocked_data(1, blocked_tiles)

        assert len(blocked_set) == 2
        assert exit_count == 0
        assert len(exit_tiles) == 0

    def test_build_blocked_data_empty_list(self) -> None:
        """Test _build_blocked_data con lista vacía."""
        blocked_set, exit_count, exit_tiles = MapMetadataLoader.build_blocked_data(1, [])

        assert len(blocked_set) == 0
        assert exit_count == 0
        assert len(exit_tiles) == 0

    def test_build_blocked_data_invalid_coords(self) -> None:
        """Test _build_blocked_data con coordenadas inválidas."""
        blocked_tiles = [
            {"x": "invalid", "y": 20},  # x inválido
            {"x": 10, "y": "invalid"},  # y inválido
            {"x": 10, "y": 20},  # Válido
        ]

        blocked_set, _exit_count, _exit_tiles = MapMetadataLoader.build_blocked_data(
            1, blocked_tiles
        )

        # Solo debe incluir el tile válido
        assert (10, 20) in blocked_set
        assert len(blocked_set) == 1


class TestMapManagerCoerceInt:
    """Tests para _coerce_int."""

    def test_coerce_int_valid_int(self) -> None:
        """Test _coerce_int con entero válido."""
        assert MapMetadataLoader.coerce_int(42) == 42
        assert MapMetadataLoader.coerce_int(0) == 0
        assert MapMetadataLoader.coerce_int(-10) == -10

    def test_coerce_int_string_number(self) -> None:
        """Test _coerce_int con string numérico."""
        assert MapMetadataLoader.coerce_int("42") == 42
        assert MapMetadataLoader.coerce_int("0") == 0

    def test_coerce_int_invalid_string(self) -> None:
        """Test _coerce_int con string inválido."""
        assert MapMetadataLoader.coerce_int("invalid") is None
        assert MapMetadataLoader.coerce_int("abc123") is None

    def test_coerce_int_none(self) -> None:
        """Test _coerce_int con None."""
        assert MapMetadataLoader.coerce_int(None) is None

    def test_coerce_int_float(self) -> None:
        """Test _coerce_int con float."""
        assert MapMetadataLoader.coerce_int(42.5) == 42  # Trunca
        assert MapMetadataLoader.coerce_int(42.9) == 42

    def test_coerce_int_list(self) -> None:
        """Test _coerce_int con lista (inválido)."""
        assert MapMetadataLoader.coerce_int([1, 2, 3]) is None

    def test_coerce_int_dict(self) -> None:
        """Test _coerce_int con dict (inválido)."""
        assert MapMetadataLoader.coerce_int({"key": "value"}) is None


class TestMapManagerLoadMapDataEdgeCases:
    """Tests para casos edge de load_map_data."""

    def test_load_map_data_with_transitions_file(self, map_manager: MapManager) -> None:
        """Test load_map_data carga transiciones desde archivo separado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Metadata
            metadata_path = Path(tmpdir) / "metadata_001-064.json"
            metadata = {"w": 100, "h": 100}
            with metadata_path.open("w") as f:
                json.dump(metadata, f)

            # Blocked
            blocked_path = Path(tmpdir) / "blocked_001-050.json"
            blocked_path.write_text("[]")

            # Transitions
            transitions_path = Path(tmpdir) / "transitions_001-050.json"
            transitions_data = {
                "transitions": [
                    {
                        "from_map": 1,
                        "exits": [{"x": 50, "y": 1, "to_map": 2, "to_x": 50, "to_y": 99}],
                    }
                ]
            }
            with transitions_path.open("w") as f:
                json.dump(transitions_data, f)

            map_manager.load_map_data(1, metadata_path)

            # Verificar que se cargó la transición
            exit_tile = map_manager.get_exit_tile(1, 50, 1)
            assert exit_tile is not None
            assert exit_tile["to_map"] == 2

    def test_load_map_data_error_handling(self, map_manager: MapManager) -> None:
        """Test load_map_data maneja errores correctamente."""
        # Archivo que no existe
        nonexistent_path = Path("/nonexistent/metadata.json")
        map_manager.load_map_data(999, nonexistent_path)

        # No debe crashear, debe usar valores por defecto
        size = map_manager.get_map_size(999)
        assert size == (100, 100)  # Valores por defecto

    def test_load_map_data_different_ranges(self, map_manager: MapManager) -> None:
        """Test load_map_data con diferentes rangos de mapas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mapa en rango 1 (1-50)
            metadata_path_1 = Path(tmpdir) / "metadata_001-064.json"
            metadata_1 = {"w": 100, "h": 100}
            with metadata_path_1.open("w") as f:
                json.dump(metadata_1, f)
            blocked_path_1 = Path(tmpdir) / "blocked_001-050.json"
            blocked_path_1.write_text("[]")

            # Mapa en rango 2 (51-100)
            metadata_path_2 = Path(tmpdir) / "metadata_051-100.json"
            metadata_2 = {"w": 120, "h": 120}
            with metadata_path_2.open("w") as f:
                json.dump(metadata_2, f)
            blocked_path_2 = Path(tmpdir) / "blocked_051-100.json"
            blocked_path_2.write_text("[]")

            map_manager.load_map_data(1, metadata_path_1)
            map_manager.load_map_data(75, metadata_path_2)

            assert map_manager.get_map_size(1) == (100, 100)
            assert map_manager.get_map_size(75) == (120, 120)
