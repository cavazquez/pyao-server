"""Tests adicionales para métodos de procesamiento de MapResourcesService."""

import json
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest

from src.services.map.map_resources_service import MapResourcesService


@pytest.fixture
def temp_map_dir():
    """Crea un directorio temporal para archivos de mapas.

    Yields:
        Path: Directorio temporal para tests.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestProcessBlockedFilePerFile:
    """Tests para _process_blocked_file_per_file."""

    def test_process_blocked_file_per_file_blocked_tiles(self, temp_map_dir):
        """Test procesamiento de tiles bloqueados."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "b", "x": 10, "y": 20}) + "\n")
            f.write(json.dumps({"m": 1, "t": "b", "x": 15, "y": 25}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        assert (10, 20) in blocked_by_map[1]
        assert (15, 25) in blocked_by_map[1]

    def test_process_blocked_file_per_file_water_tiles(self, temp_map_dir):
        """Test procesamiento de tiles de agua."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "w", "x": 5, "y": 5}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        assert (5, 5) in water_by_map[1]
        assert (5, 5) in blocked_by_map[1]  # Agua también bloquea

    def test_process_blocked_file_per_file_tree_tiles(self, temp_map_dir):
        """Test procesamiento de tiles de árboles."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "t", "x": 30, "y": 30}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        assert (30, 30) in trees_by_map[1]
        assert (30, 30) in blocked_by_map[1]  # Árboles también bloquean

    def test_process_blocked_file_per_file_mine_tiles(self, temp_map_dir):
        """Test procesamiento de tiles de minas."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "m", "x": 40, "y": 40}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        assert (40, 40) in mines_by_map[1]
        assert (40, 40) in blocked_by_map[1]  # Minas también bloquean

    def test_process_blocked_file_per_file_invalid_json(self, temp_map_dir):
        """Test procesamiento con JSON inválido."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write("invalid json {}\n")
            f.write(json.dumps({"m": 1, "t": "b", "x": 10, "y": 20}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        # Debe ignorar la línea inválida y procesar la válida
        assert (10, 20) in blocked_by_map[1]

    def test_process_blocked_file_per_file_invalid_map_id(self, temp_map_dir):
        """Test procesamiento con map_id inválido."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": "invalid", "t": "b", "x": 10, "y": 20}) + "\n")
            f.write(json.dumps({"m": 1, "t": "b", "x": 15, "y": 25}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        # Solo debe procesar la válida
        assert (15, 25) in blocked_by_map[1]
        assert 1 in blocked_by_map

    def test_process_blocked_file_per_file_invalid_coords(self, temp_map_dir):
        """Test procesamiento con coordenadas inválidas."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "b", "x": "invalid", "y": 20}) + "\n")
            f.write(json.dumps({"m": 1, "t": "b", "x": 15, "y": 25}) + "\n")

        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        # Solo debe procesar la válida
        assert (15, 25) in blocked_by_map[1]

    def test_process_blocked_file_per_file_nonexistent(self):
        """Test procesamiento con archivo inexistente."""
        nonexistent_path = Path("/nonexistent/blocked.json")
        blocked_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        water_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        trees_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)
        mines_by_map: dict[int, set[tuple[int, int]]] = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            nonexistent_path, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        # No debe hacer nada
        assert len(blocked_by_map) == 0


class TestProcessObjectsFilePerFile:
    """Tests para _process_objects_file_per_file."""

    def test_process_objects_file_per_file_tree(self, temp_map_dir):
        """Test procesamiento de árboles desde objects."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "tree", "x": 30, "y": 30}) + "\n")

        trees_by_map: dict[int, set[tuple[int, int]]] = {}
        mines_by_map: dict[int, set[tuple[int, int]]] = {}
        blocked_by_map: dict[int, set[tuple[int, int]]] = {}
        signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
        doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
        water_by_map: dict[int, set[tuple[int, int]]] = {}
        anvils_by_map: dict[int, set[tuple[int, int]]] = {}
        forges_by_map: dict[int, set[tuple[int, int]]] = {}

        MapResourcesService._process_objects_file_per_file(
            objects_path,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
        )

        assert (30, 30) in trees_by_map[1]
        assert (30, 30) in blocked_by_map[1]

    def test_process_objects_file_per_file_anvil_forge(self, temp_map_dir):
        """Test procesamiento de yunques y fraguas."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "anvil", "x": 50, "y": 50}) + "\n")
            f.write(json.dumps({"m": 1, "t": "forge", "x": 60, "y": 60}) + "\n")

        trees_by_map: dict[int, set[tuple[int, int]]] = {}
        mines_by_map: dict[int, set[tuple[int, int]]] = {}
        blocked_by_map: dict[int, set[tuple[int, int]]] = {}
        signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
        doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
        water_by_map: dict[int, set[tuple[int, int]]] = {}
        anvils_by_map: dict[int, set[tuple[int, int]]] = {}
        forges_by_map: dict[int, set[tuple[int, int]]] = {}

        MapResourcesService._process_objects_file_per_file(
            objects_path,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
        )

        assert (50, 50) in anvils_by_map[1]
        assert (60, 60) in forges_by_map[1]
        assert (50, 50) in blocked_by_map[1]
        assert (60, 60) in blocked_by_map[1]

    def test_process_objects_file_per_file_water(self, temp_map_dir):
        """Test procesamiento de agua desde objects."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "water", "x": 5, "y": 5}) + "\n")

        trees_by_map: dict[int, set[tuple[int, int]]] = {}
        mines_by_map: dict[int, set[tuple[int, int]]] = {}
        blocked_by_map: dict[int, set[tuple[int, int]]] = {}
        signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
        doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
        water_by_map: dict[int, set[tuple[int, int]]] = {}
        anvils_by_map: dict[int, set[tuple[int, int]]] = {}
        forges_by_map: dict[int, set[tuple[int, int]]] = {}

        MapResourcesService._process_objects_file_per_file(
            objects_path,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
        )

        assert (5, 5) in water_by_map[1]
        # Agua NO bloquea cuando viene de objects (no se agrega a blocked)
        if 1 in blocked_by_map:
            assert (5, 5) not in blocked_by_map[1]

    def test_process_objects_file_per_file_sign_door(self, temp_map_dir):
        """Test procesamiento de carteles y puertas."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "sign", "x": 70, "y": 70, "g": 1001}) + "\n")
            f.write(json.dumps({"m": 1, "t": "door", "x": 80, "y": 80, "g": 2001}) + "\n")

        trees_by_map: dict[int, set[tuple[int, int]]] = {}
        mines_by_map: dict[int, set[tuple[int, int]]] = {}
        blocked_by_map: dict[int, set[tuple[int, int]]] = {}
        signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
        doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
        water_by_map: dict[int, set[tuple[int, int]]] = {}
        anvils_by_map: dict[int, set[tuple[int, int]]] = {}
        forges_by_map: dict[int, set[tuple[int, int]]] = {}

        MapResourcesService._process_objects_file_per_file(
            objects_path,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
        )

        assert (70, 70) in signs_by_map[1]
        assert signs_by_map[1][70, 70] == 1001
        assert (80, 80) in doors_by_map[1]
        assert doors_by_map[1][80, 80] == 2001

    def test_process_objects_file_per_file_sign_invalid_grh(self, temp_map_dir):
        """Test procesamiento de cartel con grh inválido."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "sign", "x": 70, "y": 70, "g": "invalid"}) + "\n")
            f.write(json.dumps({"m": 1, "t": "sign", "x": 75, "y": 75, "g": 1001}) + "\n")

        trees_by_map: dict[int, set[tuple[int, int]]] = {}
        mines_by_map: dict[int, set[tuple[int, int]]] = {}
        blocked_by_map: dict[int, set[tuple[int, int]]] = {}
        signs_by_map: dict[int, dict[tuple[int, int], int]] = {}
        doors_by_map: dict[int, dict[tuple[int, int], int]] = {}
        water_by_map: dict[int, set[tuple[int, int]]] = {}
        anvils_by_map: dict[int, set[tuple[int, int]]] = {}
        forges_by_map: dict[int, set[tuple[int, int]]] = {}

        MapResourcesService._process_objects_file_per_file(
            objects_path,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
        )

        # Solo debe cargar el válido
        assert (75, 75) in signs_by_map[1]
        assert (70, 70) not in signs_by_map[1]


class TestFindFileForMap:
    """Tests para _find_file_for_map."""

    def test_find_file_for_map_found(self, temp_map_dir):
        """Test encontrar archivo para un mapa."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("[]")

        found = service._find_file_for_map("blocked_*.json", 25)

        assert found == blocked_file

    def test_find_file_for_map_not_found(self, temp_map_dir):
        """Test no encontrar archivo para un mapa fuera de rango."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("[]")

        found = service._find_file_for_map("blocked_*.json", 999)

        assert found is None

    def test_find_file_for_map_invalid_filename(self, temp_map_dir):
        """Test con nombre de archivo inválido."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        blocked_file = temp_map_dir / "blocked_invalid.json"
        blocked_file.write_text("[]")

        found = service._find_file_for_map("blocked_*.json", 1)

        assert found is None


class TestProcessBlockedFile:
    """Tests para _process_blocked_file."""

    def test_process_blocked_file_valid(self, temp_map_dir):
        """Test procesamiento de archivo blocked válido."""
        blocked_path = temp_map_dir / "blocked_1-50.json"
        with blocked_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "b", "x": 10, "y": 20}) + "\n")
            f.write(json.dumps({"m": 1, "t": "w", "x": 5, "y": 5}) + "\n")
            f.write(json.dumps({"m": 2, "t": "b", "x": 15, "y": 25}) + "\n")  # Mapa diferente

        blocked, water, _trees, _mines = MapResourcesService._process_blocked_file(blocked_path, 1)

        assert (10, 20) in blocked
        assert (5, 5) in water
        assert (5, 5) in blocked  # Agua también bloquea
        assert (15, 25) not in blocked  # Mapa diferente

    def test_process_blocked_file_nonexistent(self):
        """Test procesamiento con archivo inexistente."""
        blocked, water, trees, mines = MapResourcesService._process_blocked_file(None, 1)

        assert len(blocked) == 0
        assert len(water) == 0
        assert len(trees) == 0
        assert len(mines) == 0


class TestProcessObjectsFile:
    """Tests para _process_objects_file."""

    def test_process_objects_file_valid(self, temp_map_dir):
        """Test procesamiento de archivo objects válido."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "tree", "x": 30, "y": 30}) + "\n")
            f.write(json.dumps({"m": 1, "t": "anvil", "x": 50, "y": 50}) + "\n")
            f.write(json.dumps({"m": 2, "t": "tree", "x": 40, "y": 40}) + "\n")  # Mapa diferente

        trees: set[tuple[int, int]] = set()
        mines: set[tuple[int, int]] = set()
        blocked: set[tuple[int, int]] = set()
        water: set[tuple[int, int]] = set()
        anvils: set[tuple[int, int]] = set()
        forges: set[tuple[int, int]] = set()

        MapResourcesService._process_objects_file(
            objects_path, 1, trees, mines, blocked, water, anvils, forges
        )

        assert (30, 30) in trees
        assert (50, 50) in anvils
        assert (30, 30) in blocked
        assert (50, 50) in blocked
        assert (40, 40) not in trees  # Mapa diferente

    def test_process_objects_file_nonexistent(self):
        """Test procesamiento con archivo inexistente."""
        trees: set[tuple[int, int]] = set()
        mines: set[tuple[int, int]] = set()
        blocked: set[tuple[int, int]] = set()
        water: set[tuple[int, int]] = set()
        anvils: set[tuple[int, int]] = set()
        forges: set[tuple[int, int]] = set()

        MapResourcesService._process_objects_file(
            None, 1, trees, mines, blocked, water, anvils, forges
        )

        assert len(trees) == 0
        assert len(anvils) == 0


class TestLoadMap:
    """Tests para _load_map."""

    def test_load_map_with_both_files(self, temp_map_dir):
        """Test carga de mapa con ambos archivos."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Crear archivos
        blocked_file = temp_map_dir / "blocked_1-50.json"
        with blocked_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "b", "x": 10, "y": 20}) + "\n")

        objects_file = temp_map_dir / "objects_1-50.json"
        with objects_file.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "tree", "x": 30, "y": 30}) + "\n")
            f.write(json.dumps({"m": 1, "t": "sign", "x": 70, "y": 70, "g": 1001}) + "\n")
            f.write(json.dumps({"m": 1, "t": "door", "x": 80, "y": 80, "g": 2001}) + "\n")

        service._load_map(1)

        assert "map_1" in service.resources
        assert (10, 20) in service.resources["map_1"]["blocked"]
        assert (30, 30) in service.resources["map_1"]["trees"]
        assert "map_1" in service.signs
        assert (70, 70) in service.signs["map_1"]
        assert "map_1" in service.doors
        assert (80, 80) in service.doors["map_1"]

    def test_load_map_no_files(self, temp_map_dir):
        """Test carga de mapa sin archivos."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service._load_map(999)

        assert "map_999" not in service.resources

    def test_load_map_exception_handling(self, temp_map_dir):
        """Test manejo de excepciones en _load_map."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Crear archivo que cause error al leer
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("invalid json {")

        # No debe crashear
        service._load_map(1)
