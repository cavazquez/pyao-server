"""Tests para exit tiles en MapManager."""

import json
import tempfile
from pathlib import Path

from src.game.map_manager import MapManager


class TestMapManagerExitTiles:
    """Tests para sistema de exit tiles."""

    def test_load_exit_tiles_from_json(self) -> None:
        """Test que los exit tiles se cargan correctamente desde JSON."""
        # Setup - Crear archivo temporal con exit tiles
        map_data = {
            "id": 1,
            "name": "Test Map",
            "width": 100,
            "height": 100,
            "blocked_tiles": [
                {"x": 50, "y": 1, "type": "exit", "to_map": 2, "to_x": 50, "to_y": 99},
                {"x": 1, "y": 50, "type": "exit", "to_map": 3, "to_x": 99, "to_y": 50},
                {"x": 30, "y": 30, "type": "building"},
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(map_data, f)
            temp_path = Path(f.name)

        try:
            # Execute
            map_manager = MapManager()
            map_manager.load_map_data(1, temp_path)

            # Assert - Exit tiles cargados
            exit_1 = map_manager.get_exit_tile(1, 50, 1)
            assert exit_1 is not None
            assert exit_1["to_map"] == 2
            assert exit_1["to_x"] == 50
            assert exit_1["to_y"] == 99

            exit_2 = map_manager.get_exit_tile(1, 1, 50)
            assert exit_2 is not None
            assert exit_2["to_map"] == 3
            assert exit_2["to_x"] == 99
            assert exit_2["to_y"] == 50

            # Assert - Tile normal no es exit
            normal_tile = map_manager.get_exit_tile(1, 30, 30)
            assert normal_tile is None

        finally:
            # Cleanup
            temp_path.unlink()

    def test_exit_tiles_block_movement(self) -> None:
        """Test que los exit tiles también bloquean el movimiento normal."""
        # Setup
        map_data = {
            "id": 1,
            "name": "Test Map",
            "width": 100,
            "height": 100,
            "blocked_tiles": [
                {"x": 50, "y": 1, "type": "exit", "to_map": 2, "to_x": 50, "to_y": 99},
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(map_data, f)
            temp_path = Path(f.name)

        try:
            # Execute
            map_manager = MapManager()
            map_manager.load_map_data(1, temp_path)

            # Assert - Exit tile bloquea movimiento
            can_move = map_manager.can_move_to(1, 50, 1)
            assert can_move is False

        finally:
            # Cleanup
            temp_path.unlink()

    def test_get_exit_tile_returns_none_for_invalid_position(self) -> None:
        """Test que get_exit_tile retorna None para posiciones inválidas."""
        # Setup
        map_manager = MapManager()

        # Execute & Assert
        exit_tile = map_manager.get_exit_tile(1, 50, 50)
        assert exit_tile is None

        exit_tile = map_manager.get_exit_tile(999, 1, 1)
        assert exit_tile is None

    def test_load_multiple_exit_tiles_same_map(self) -> None:
        """Test que se pueden cargar múltiples exit tiles en el mismo mapa."""
        # Setup
        map_data = {
            "id": 1,
            "name": "Test Map",
            "width": 100,
            "height": 100,
            "blocked_tiles": [
                {"x": 50, "y": 1, "type": "exit", "to_map": 2, "to_x": 50, "to_y": 99},
                {"x": 1, "y": 50, "type": "exit", "to_map": 3, "to_x": 99, "to_y": 50},
                {"x": 100, "y": 50, "type": "exit", "to_map": 4, "to_x": 1, "to_y": 50},
                {"x": 50, "y": 100, "type": "exit", "to_map": 5, "to_x": 50, "to_y": 1},
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(map_data, f)
            temp_path = Path(f.name)

        try:
            # Execute
            map_manager = MapManager()
            map_manager.load_map_data(1, temp_path)

            # Assert - Todos los exits cargados correctamente
            assert map_manager.get_exit_tile(1, 50, 1)["to_map"] == 2
            assert map_manager.get_exit_tile(1, 1, 50)["to_map"] == 3
            assert map_manager.get_exit_tile(1, 100, 50)["to_map"] == 4
            assert map_manager.get_exit_tile(1, 50, 100)["to_map"] == 5

        finally:
            # Cleanup
            temp_path.unlink()

    def test_exit_tile_without_required_fields_is_ignored(self) -> None:
        """Test que exit tiles sin campos requeridos son ignorados."""
        # Setup - Exit sin to_x
        map_data = {
            "id": 1,
            "name": "Test Map",
            "width": 100,
            "height": 100,
            "blocked_tiles": [
                {"x": 50, "y": 1, "type": "exit", "to_map": 2, "to_y": 99},  # Falta to_x
            ],
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(map_data, f)
            temp_path = Path(f.name)

        try:
            # Execute
            map_manager = MapManager()
            map_manager.load_map_data(1, temp_path)

            # Assert - Exit no cargado (falta campo requerido)
            exit_tile = map_manager.get_exit_tile(1, 50, 1)
            assert exit_tile is None

            # Assert - Pero sí está bloqueado
            can_move = map_manager.can_move_to(1, 50, 1)
            assert can_move is False

        finally:
            # Cleanup
            temp_path.unlink()

    def test_different_maps_have_independent_exit_tiles(self) -> None:
        """Test que diferentes mapas tienen exit tiles independientes."""
        # Setup
        map_manager = MapManager()

        map_1_data = {
            "id": 1,
            "name": "Map 1",
            "width": 100,
            "height": 100,
            "blocked_tiles": [
                {"x": 50, "y": 1, "type": "exit", "to_map": 2, "to_x": 50, "to_y": 99},
            ],
        }

        map_2_data = {
            "id": 2,
            "name": "Map 2",
            "width": 100,
            "height": 100,
            "blocked_tiles": [
                {"x": 50, "y": 99, "type": "exit", "to_map": 1, "to_x": 50, "to_y": 1},
            ],
        }

        with (
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f1,
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f2,
        ):
            json.dump(map_1_data, f1)
            json.dump(map_2_data, f2)
            temp_path_1 = Path(f1.name)
            temp_path_2 = Path(f2.name)

        try:
            # Execute
            map_manager.load_map_data(1, temp_path_1)
            map_manager.load_map_data(2, temp_path_2)

            # Assert - Cada mapa tiene su exit
            exit_map_1 = map_manager.get_exit_tile(1, 50, 1)
            assert exit_map_1 is not None
            assert exit_map_1["to_map"] == 2

            exit_map_2 = map_manager.get_exit_tile(2, 50, 99)
            assert exit_map_2 is not None
            assert exit_map_2["to_map"] == 1

            # Assert - Los exits no se mezclan
            assert map_manager.get_exit_tile(1, 50, 99) is None
            assert map_manager.get_exit_tile(2, 50, 1) is None

        finally:
            # Cleanup
            temp_path_1.unlink()
            temp_path_2.unlink()
