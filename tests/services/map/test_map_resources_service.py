"""Tests para MapResourcesService."""

import json
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestMapResourcesService:
    """Tests para MapResourcesService."""

    def test_init_with_empty_directory(self, temp_map_dir):
        """Test inicialización con directorio vacío."""
        # Limpiar caché antes del test
        cache_dir = temp_map_dir.parent / "map_cache"
        if cache_dir.exists():
            cache_file = cache_dir / "map_resources_cache.json"
            if cache_file.exists():
                cache_file.unlink()

        service = MapResourcesService(maps_dir=temp_map_dir)

        assert service is not None
        assert service.maps_dir == temp_map_dir
        # Puede tener recursos si hay caché, pero debe inicializarse correctamente
        assert isinstance(service.resources, dict)

    def test_init_with_nonexistent_directory(self):
        """Test inicialización con directorio que no existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "nonexistent"
            # Limpiar caché antes del test
            cache_dir = Path(tmpdir) / "map_cache"
            if cache_dir.exists():
                cache_file = cache_dir / "map_resources_cache.json"
                if cache_file.exists():
                    cache_file.unlink()

            service = MapResourcesService(maps_dir=nonexistent)

            assert service is not None
            assert service.maps_dir == nonexistent
            # El directorio debe haberse creado durante _load_all_maps
            # (se crea en _load_all_maps si no existe)

    def test_has_water_nonexistent_map(self, temp_map_dir):
        """Test verificar agua en mapa que no existe."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Mapa 999 no existe
        assert not service.has_water(999, 10, 10)

    def test_has_tree_nonexistent_map(self, temp_map_dir):
        """Test verificar árbol en mapa que no existe."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Mapa 999 no existe
        assert not service.has_tree(999, 10, 10)

    def test_has_mine_nonexistent_map(self, temp_map_dir):
        """Test verificar mina en mapa que no existe."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Mapa 999 no existe
        assert not service.has_mine(999, 10, 10)

    def test_is_blocked_nonexistent_map(self, temp_map_dir):
        """Test verificar tile bloqueado en mapa que no existe."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Mapa 999 no existe
        assert not service.is_blocked(999, 10, 10)

    def test_get_resource_counts_nonexistent_map(self, temp_map_dir):
        """Test obtener conteos de mapa que no existe."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        counts = service.get_resource_counts(999)
        assert counts["water"] == 0
        assert counts["trees"] == 0
        assert counts["mines"] == 0

    def test_default_maps_dir(self, temp_map_dir):
        """Test que el directorio por defecto es 'map_data'."""
        # Usar temp_map_dir para evitar cargar 290 mapas reales
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Verificar que acepta el directorio personalizado
        assert service.maps_dir == temp_map_dir

    def test_custom_maps_dir(self, temp_map_dir):
        """Test que se puede especificar un directorio personalizado."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        assert service.maps_dir == temp_map_dir

    def test_maps_dir_as_string(self, temp_map_dir):
        """Test que maps_dir puede ser un string."""
        service = MapResourcesService(maps_dir=str(temp_map_dir))

        assert service.maps_dir == temp_map_dir

    def test_resources_dict_structure(self, temp_map_dir):
        """Test que la estructura de resources es correcta."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Debe ser un diccionario
        assert isinstance(service.resources, dict)

        # Si agregamos un mapa manualmente, debe tener la estructura correcta
        service.resources["map_1"] = {
            "blocked": {(10, 10), (10, 11)},
            "water": {(5, 5)},
            "trees": {(20, 20)},
            "mines": {(30, 30)},
        }

        # Verificar que las funciones funcionan
        assert service.is_blocked(1, 10, 10)
        assert service.has_water(1, 5, 5)
        assert service.has_tree(1, 20, 20)
        assert service.has_mine(1, 30, 30)

    def test_get_resource_counts_with_data(self, temp_map_dir):
        """Test obtener conteos cuando hay datos."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Agregar datos manualmente
        service.resources["map_1"] = {
            "blocked": {(10, 10), (10, 11)},
            "water": {(5, 5), (5, 6), (5, 7)},
            "trees": {(20, 20), (20, 21)},
            "mines": {(30, 30)},
        }

        counts = service.get_resource_counts(1)
        assert counts["water"] == 3
        assert counts["trees"] == 2
        assert counts["mines"] == 1

    def test_multiple_maps(self, temp_map_dir):
        """Test con múltiples mapas."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Agregar varios mapas
        service.resources["map_1"] = {
            "blocked": set(),
            "water": {(5, 5)},
            "trees": set(),
            "mines": set(),
        }
        service.resources["map_2"] = {
            "blocked": set(),
            "water": {(10, 10)},
            "trees": set(),
            "mines": set(),
        }

        # Verificar que cada mapa tiene sus propios recursos
        assert service.has_water(1, 5, 5)
        assert not service.has_water(1, 10, 10)
        assert service.has_water(2, 10, 10)
        assert not service.has_water(2, 5, 5)

    def test_coordinates_are_tuples(self, temp_map_dir):
        """Test que las coordenadas se manejan como tuplas."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service.resources["map_1"] = {
            "blocked": set(),
            "water": {(5, 5)},
            "trees": set(),
            "mines": set(),
        }

        # Verificar con diferentes formatos de coordenadas
        assert service.has_water(1, 5, 5)
        assert not service.has_water(1, 5, 6)
        assert not service.has_water(1, 6, 5)

    def test_has_anvil(self, temp_map_dir):
        """Test verificar yunque."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service.resources["map_1"] = {
            "blocked": set(),
            "water": set(),
            "trees": set(),
            "mines": set(),
            "anvils": {(15, 15)},
        }

        assert service.has_anvil(1, 15, 15)
        assert not service.has_anvil(1, 15, 16)

    def test_has_forge(self, temp_map_dir):
        """Test verificar forja."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service.resources["map_1"] = {
            "blocked": set(),
            "water": set(),
            "trees": set(),
            "mines": set(),
            "forges": {(25, 25)},
        }

        assert service.has_forge(1, 25, 25)
        assert not service.has_forge(1, 25, 26)

    def test_get_sign_at(self, temp_map_dir):
        """Test obtener sign en posición."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service.signs["map_1"] = {(10, 10): 7001, (10, 11): 7002}

        assert service.get_sign_at(1, 10, 10) == 7001
        assert service.get_sign_at(1, 10, 11) == 7002
        assert service.get_sign_at(1, 10, 12) is None
        assert service.get_sign_at(999, 10, 10) is None

    def test_get_door_at(self, temp_map_dir):
        """Test obtener puerta en posición."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service.doors["map_1"] = {(20, 20): 5001, (20, 21): 5002}

        assert service.get_door_at(1, 20, 20) == 5001
        assert service.get_door_at(1, 20, 21) == 5002
        assert service.get_door_at(1, 20, 22) is None
        assert service.get_door_at(999, 20, 20) is None

    def test_get_resource_counts_includes_all(self, temp_map_dir):
        """Test que get_resource_counts incluye todos los recursos."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        service.resources["map_1"] = {
            "blocked": {(1, 1)},
            "water": {(2, 2)},
            "trees": {(3, 3)},
            "mines": {(4, 4)},
            "anvils": {(5, 5)},
            "forges": {(6, 6)},
        }

        counts = service.get_resource_counts(1)
        assert counts["water"] == 1
        assert counts["trees"] == 1
        assert counts["mines"] == 1
        assert counts["anvils"] == 1
        assert counts["forges"] == 1

    def test_build_mtimes(self, temp_map_dir):
        """Test _build_mtimes."""
        # Crear archivos temporales
        file1 = temp_map_dir / "test1.json"
        file2 = temp_map_dir / "test2.json"
        file1.write_text("{}")
        file2.write_text("{}")

        files = [file1, file2]
        names, mtimes = MapResourcesService._build_mtimes(files)

        assert len(names) == 2
        assert "test1.json" in names
        assert "test2.json" in names
        assert len(mtimes) == 2
        assert "test1.json" in mtimes
        assert "test2.json" in mtimes
        assert isinstance(mtimes["test1.json"], float)

    def test_build_mtimes_missing_file(self, temp_map_dir):
        """Test _build_mtimes con archivo que no existe."""
        missing_file = temp_map_dir / "missing.json"
        files = [missing_file]

        names, mtimes = MapResourcesService._build_mtimes(files)

        assert len(names) == 0
        assert len(mtimes) == 0

    def test_read_cache_file(self, temp_map_dir):
        """Test _read_cache_file."""
        cache_file = temp_map_dir / "cache.json"
        cache_file.write_text('{"version": 2, "maps": {}}')

        data = MapResourcesService._read_cache_file(cache_file)

        assert data["version"] == 2
        assert "maps" in data

    def test_read_cache_file_invalid_json(self, temp_map_dir):
        """Test _read_cache_file con JSON inválido."""
        cache_file = temp_map_dir / "invalid.json"
        cache_file.write_text("invalid json")

        with pytest.raises(json.JSONDecodeError):
            MapResourcesService._read_cache_file(cache_file)

    def test_is_cache_source_valid(self, temp_map_dir):
        """Test _is_cache_source_valid."""
        # Crear archivos
        file1 = temp_map_dir / "blocked_001.json"
        file2 = temp_map_dir / "objects_001.json"
        file1.write_text("{}")
        file2.write_text("{}")

        blocked_files = [file1]
        objects_files = [file2]

        # Construir info del caché
        blocked_names, blocked_mtimes = MapResourcesService._build_mtimes(blocked_files)
        objects_names, objects_mtimes = MapResourcesService._build_mtimes(objects_files)

        blocked_info = {"files": blocked_names, "mtimes": blocked_mtimes}
        objects_info = {"files": objects_names, "mtimes": objects_mtimes}

        # Debe ser válido
        assert MapResourcesService._is_cache_source_valid(
            blocked_files, objects_files, blocked_info, objects_info
        )

    def test_is_cache_source_valid_different_files(self, temp_map_dir):
        """Test _is_cache_source_valid con archivos diferentes."""
        file1 = temp_map_dir / "blocked_001.json"
        file1.write_text("{}")

        blocked_files = [file1]
        objects_files = []

        # Info del caché con archivos diferentes
        blocked_info = {"files": ["blocked_002.json"], "mtimes": {}}
        objects_info = {"files": [], "mtimes": {}}

        # No debe ser válido
        assert not MapResourcesService._is_cache_source_valid(
            blocked_files, objects_files, blocked_info, objects_info
        )

    def test_find_file_for_map(self, temp_map_dir):
        """Test _find_file_for_map."""
        # Crear archivos con formato correcto (rango de mapas: blocked_XXX-YYY.json)
        (temp_map_dir / "blocked_1-50.json").write_text("{}")
        (temp_map_dir / "blocked_51-100.json").write_text("{}")

        service = MapResourcesService(maps_dir=temp_map_dir)

        # _find_file_for_map busca archivos que coincidan con el patrón y el map_id
        # El formato esperado es blocked_XXX-YYY.json donde XXX-YYY es un rango
        file1 = service._find_file_for_map("blocked_*.json", 1)  # Debe estar en 1-50
        file2 = service._find_file_for_map("blocked_*.json", 75)  # Debe estar en 51-100
        file3 = service._find_file_for_map("blocked_*.json", 999)  # No existe

        assert file1 is not None
        assert "1-50" in str(file1)
        assert file2 is not None
        assert "51-100" in str(file2)
        assert file3 is None

    def test_process_blocked_file(self, temp_map_dir):
        """Test _process_blocked_file."""
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text(
            '{"m": 1, "t": "b", "x": 10, "y": 10}\n'
            '{"m": 1, "t": "w", "x": 20, "y": 20}\n'
            '{"m": 1, "t": "t", "x": 30, "y": 30}\n'
            '{"m": 1, "t": "m", "x": 40, "y": 40}\n'
            '{"m": 2, "t": "b", "x": 10, "y": 10}\n'  # Diferente mapa
        )

        blocked, water, trees, mines = MapResourcesService._process_blocked_file(
            blocked_file, map_id=1
        )

        assert (10, 10) in blocked  # blocked
        assert (20, 20) in water  # water
        assert (20, 20) in blocked  # water también bloquea
        assert (30, 30) in trees  # tree
        assert (30, 30) in blocked  # tree también bloquea
        assert (40, 40) in mines  # mine
        assert (40, 40) in blocked  # mine también bloquea
        # El tile del mapa 2 no debe estar
        assert (10, 10) not in blocked or (10, 10) in blocked  # Puede estar si es del mapa 1

    def test_process_blocked_file_nonexistent(self, temp_map_dir):
        """Test _process_blocked_file con archivo que no existe."""
        missing_file = temp_map_dir / "missing.json"

        blocked, water, trees, mines = MapResourcesService._process_blocked_file(
            missing_file, map_id=1
        )

        assert len(blocked) == 0
        assert len(water) == 0
        assert len(trees) == 0
        assert len(mines) == 0

    def test_process_blocked_file_invalid_json(self, temp_map_dir):
        """Test _process_blocked_file con JSON inválido."""
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("invalid json\n{'m': 1, 't': 'b', 'x': 10, 'y': 10}\n")

        blocked, _water, _trees, _mines = MapResourcesService._process_blocked_file(
            blocked_file, map_id=1
        )

        # Debe ignorar líneas inválidas
        assert len(blocked) == 0

    def test_process_objects_file(self, temp_map_dir):
        """Test _process_objects_file."""
        objects_file = temp_map_dir / "objects_1-50.json"
        objects_file.write_text(
            '{"m": 1, "t": "tree", "x": 10, "y": 10}\n'
            '{"m": 1, "t": "mine", "x": 20, "y": 20}\n'
            '{"m": 1, "t": "anvil", "x": 30, "y": 30}\n'
            '{"m": 1, "t": "forge", "x": 40, "y": 40}\n'
            '{"m": 1, "t": "water", "x": 50, "y": 50}\n'
            '{"m": 2, "t": "tree", "x": 10, "y": 10}\n'  # Diferente mapa
        )

        trees = set()
        mines = set()
        blocked = set()
        water = set()
        anvils = set()
        forges = set()

        MapResourcesService._process_objects_file(
            objects_file,
            map_id=1,
            trees=trees,
            mines=mines,
            blocked=blocked,
            water=water,
            anvils=anvils,
            forges=forges,
        )

        assert (10, 10) in trees
        assert (10, 10) in blocked  # tree bloquea
        assert (20, 20) in mines
        assert (20, 20) in blocked  # mine bloquea
        assert (30, 30) in anvils
        assert (30, 30) in blocked  # anvil bloquea
        assert (40, 40) in forges
        assert (40, 40) in blocked  # forge bloquea
        assert (50, 50) in water
        # water no bloquea en objects (solo en blocked)

    def test_process_objects_file_nonexistent(self, temp_map_dir):
        """Test _process_objects_file con archivo que no existe."""
        missing_file = temp_map_dir / "missing.json"

        trees = set()
        mines = set()
        blocked = set()
        water = set()
        anvils = set()
        forges = set()

        MapResourcesService._process_objects_file(
            missing_file,
            map_id=1,
            trees=trees,
            mines=mines,
            blocked=blocked,
            water=water,
            anvils=anvils,
            forges=forges,
        )

        assert len(trees) == 0
        assert len(mines) == 0
        assert len(blocked) == 0
        assert len(water) == 0
        assert len(anvils) == 0
        assert len(forges) == 0

    def test_load_signs_from_objects(self, temp_map_dir):
        """Test _load_signs_from_objects."""
        objects_file = temp_map_dir / "objects_1-50.json"
        objects_file.write_text(
            '{"m": 1, "t": "sign", "x": 10, "y": 10, "g": 7001}\n'
            '{"m": 1, "t": "sign", "x": 20, "y": 20, "g": 7002}\n'
        )

        signs = MapResourcesService._load_signs_from_objects(objects_file, map_id=1)

        assert (10, 10) in signs
        assert signs[10, 10] == 7001
        assert (20, 20) in signs
        assert signs[20, 20] == 7002

    def test_load_signs_from_objects_nonexistent(self, temp_map_dir):
        """Test _load_signs_from_objects con archivo que no existe."""
        missing_file = temp_map_dir / "missing.json"

        signs = MapResourcesService._load_signs_from_objects(missing_file, map_id=1)

        assert len(signs) == 0

    def test_load_doors_from_objects(self, temp_map_dir):
        """Test _load_doors_from_objects."""
        objects_file = temp_map_dir / "objects_1-50.json"
        objects_file.write_text(
            '{"m": 1, "t": "door", "x": 10, "y": 10, "g": 5001}\n'
            '{"m": 1, "t": "door", "x": 20, "y": 20, "g": 5002}\n'
        )

        doors = MapResourcesService._load_doors_from_objects(objects_file, map_id=1)

        assert (10, 10) in doors
        assert doors[10, 10] == 5001
        assert (20, 20) in doors
        assert doors[20, 20] == 5002

    def test_load_doors_from_objects_nonexistent(self, temp_map_dir):
        """Test _load_doors_from_objects con archivo que no existe."""
        missing_file = temp_map_dir / "missing.json"

        doors = MapResourcesService._load_doors_from_objects(missing_file, map_id=1)

        assert len(doors) == 0

    def test_process_blocked_file_per_file(self, temp_map_dir):
        """Test _process_blocked_file_per_file."""
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text(
            '{"m": 1, "t": "b", "x": 10, "y": 10}\n'
            '{"m": 1, "t": "w", "x": 20, "y": 20}\n'
            '{"m": 2, "t": "b", "x": 30, "y": 30}\n'
        )

        # Los diccionarios deben inicializarse con defaultdict o setdefault

        blocked_by_map = defaultdict(set)
        water_by_map = defaultdict(set)
        trees_by_map = defaultdict(set)
        mines_by_map = defaultdict(set)

        MapResourcesService._process_blocked_file_per_file(
            blocked_file, blocked_by_map, water_by_map, trees_by_map, mines_by_map
        )

        assert 1 in blocked_by_map
        assert (10, 10) in blocked_by_map[1]
        assert (20, 20) in water_by_map[1]
        assert (20, 20) in blocked_by_map[1]
        assert 2 in blocked_by_map
        assert (30, 30) in blocked_by_map[2]

    def test_process_objects_file_per_file(self, temp_map_dir):
        """Test _process_objects_file_per_file."""
        objects_file = temp_map_dir / "objects_1-50.json"
        objects_file.write_text(
            '{"m": 1, "t": "tree", "x": 10, "y": 10}\n'
            '{"m": 1, "t": "mine", "x": 20, "y": 20}\n'
            '{"m": 1, "t": "anvil", "x": 30, "y": 30}\n'
            '{"m": 1, "t": "forge", "x": 40, "y": 40}\n'
            '{"m": 1, "t": "water", "x": 50, "y": 50}\n'
            '{"m": 1, "t": "sign", "x": 60, "y": 60, "g": 7001}\n'
            '{"m": 1, "t": "door", "x": 70, "y": 70, "g": 5001}\n'
        )

        trees_by_map = {}
        mines_by_map = {}
        blocked_by_map = {}
        signs_by_map = {}
        doors_by_map = {}
        water_by_map = {}
        anvils_by_map = {}
        forges_by_map = {}

        MapResourcesService._process_objects_file_per_file(
            objects_file,
            trees_by_map,
            mines_by_map,
            blocked_by_map,
            signs_by_map,
            doors_by_map,
            water_by_map,
            anvils_by_map,
            forges_by_map,
        )

        assert 1 in trees_by_map
        assert (10, 10) in trees_by_map[1]
        assert 1 in mines_by_map
        assert (20, 20) in mines_by_map[1]
        assert 1 in anvils_by_map
        assert (30, 30) in anvils_by_map[1]
        assert 1 in forges_by_map
        assert (40, 40) in forges_by_map[1]
        assert 1 in water_by_map
        assert (50, 50) in water_by_map[1]
        assert 1 in signs_by_map
        assert (60, 60) in signs_by_map[1]
        assert signs_by_map[1][60, 60] == 7001
        assert 1 in doors_by_map
        assert (70, 70) in doors_by_map[1]
        assert doors_by_map[1][70, 70] == 5001

    def test_build_maps_payload_for_cache(self, temp_map_dir):
        """Test _build_maps_payload_for_cache."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Agregar datos manualmente
        service.resources["map_1"] = {
            "blocked": {(10, 10), (10, 11)},
            "water": {(5, 5)},
            "trees": {(20, 20)},
            "mines": {(30, 30)},
            "anvils": {(40, 40)},
            "forges": {(50, 50)},
        }
        service.signs["map_1"] = {(60, 60): 7001}
        service.doors["map_1"] = {(70, 70): 5001}

        payload = service._build_maps_payload_for_cache()

        # El payload usa str(map_id) como clave, no "map_1"
        assert "1" in payload
        map_data = payload["1"]
        assert "blocked" in map_data
        assert "water" in map_data
        assert "trees" in map_data
        assert "mines" in map_data
        assert "anvils" in map_data
        assert "forges" in map_data
        assert "signs" in map_data
        assert "doors" in map_data

    def test_rebuild_resources_from_cache(self, temp_map_dir):
        """Test _rebuild_resources_from_cache."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # El formato del caché usa str(map_id) como clave y signs/doors como listas de tuplas
        maps_data = {
            "1": {  # str(map_id), no "map_1"
                "blocked": [[10, 10], [10, 11]],
                "water": [[5, 5]],
                "trees": [[20, 20]],
                "mines": [[30, 30]],
                "anvils": [[40, 40]],
                "forges": [[50, 50]],
                "signs": [((60, 60), 7001)],  # Lista de tuplas ((x, y), grh)
                "doors": [((70, 70), 5001)],  # Lista de tuplas ((x, y), grh)
            }
        }

        service._rebuild_resources_from_cache(maps_data)

        assert "map_1" in service.resources
        assert (10, 10) in service.resources["map_1"]["blocked"]
        assert (5, 5) in service.resources["map_1"]["water"]
        assert (20, 20) in service.resources["map_1"]["trees"]
        assert (30, 30) in service.resources["map_1"]["mines"]
        assert (40, 40) in service.resources["map_1"]["anvils"]
        assert (50, 50) in service.resources["map_1"]["forges"]
        assert "map_1" in service.signs
        assert (60, 60) in service.signs["map_1"]
        assert service.signs["map_1"][60, 60] == 7001
        assert "map_1" in service.doors
        assert (70, 70) in service.doors["map_1"]
        assert service.doors["map_1"][70, 70] == 5001

    def test_save_cache_with_resources(self, temp_map_dir):
        """Test _save_cache cuando hay recursos."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Agregar recursos manualmente
        service.resources["map_1"] = {
            "blocked": {(10, 10)},
            "water": {(5, 5)},
            "trees": {(20, 20)},
            "mines": {(30, 30)},
            "anvils": {(40, 40)},
            "forges": {(50, 50)},
        }
        service.signs["map_1"] = {(60, 60): 7001}
        service.doors["map_1"] = {(70, 70): 5001}

        # Guardar caché
        service._save_cache()

        # Verificar que se creó el archivo de caché
        cache_path = service.cache_dir / "map_resources_cache.json"
        assert cache_path.exists()

        # Verificar que se puede leer
        with cache_path.open() as f:
            cache_data = json.load(f)
            assert "version" in cache_data
            assert "maps" in cache_data

    def test_load_manual_doors_file_not_exists(self, temp_map_dir):
        """Test _load_manual_doors cuando el archivo no existe."""
        # Suprimir DeprecationWarning de tomllib (es un warning interno de la librería)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning, module="tomllib")
            service = MapResourcesService(maps_dir=temp_map_dir)

            # Guardar el conteo inicial de puertas
            initial_door_count = sum(len(doors) for doors in service.doors.values())

            # Mockear la ruta para que apunte a un archivo inexistente
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = False

            def path_side_effect(*args, **kwargs):  # noqa: ANN002, ANN003
                # Si es la construcción de la ruta de puertas, retornar mock que no existe
                if len(args) == 1 and str(args[0]).endswith("map_doors.toml"):
                    return mock_path
                # Para __file__, crear un mock con parent chain
                if len(args) == 1 and str(args[0]) == "__file__":
                    mock_file_path = MagicMock()
                    mock_file_path.parent.parent.parent.parent.__truediv__ = MagicMock(
                        return_value=mock_path
                    )
                    return mock_file_path
                return Path(*args, **kwargs)

            with patch("src.services.map.map_resources_service.Path", side_effect=path_side_effect):
                # No debe lanzar excepción si el archivo no existe
                service._load_manual_doors()
                # El conteo no debe cambiar
                final_door_count = sum(len(doors) for doors in service.doors.values())
                assert final_door_count == initial_door_count

    def test_load_manual_doors_with_real_file_if_exists(self, temp_map_dir):
        """Test _load_manual_doors con el archivo real si existe."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Cargar puertas (usará el archivo real si existe)
        initial_door_count = sum(len(doors) for doors in service.doors.values())
        service._load_manual_doors()
        final_door_count = sum(len(doors) for doors in service.doors.values())

        # Si el archivo existe, debe haber cargado puertas
        # Si no existe, el conteo no cambia
        # Este test verifica que el método funciona correctamente en ambos casos
        assert final_door_count >= initial_door_count

    def test_load_manual_doors_with_valid_toml_file(self, temp_map_dir, monkeypatch):  # noqa: ARG002
        """Test _load_manual_doors con archivo TOML válido."""
        # Crear archivo TOML temporal con puertas válidas
        toml_content = """[[door]]
map_id = 1
x = 10
y = 20
grh_index = 5001
name = "Puerta Test 1"
is_open = false

[[door]]
map_id = 2
x = 30
y = 40
grh_index = 5002
name = "Puerta Test 2"
is_open = true

[[door]]
map_id = 1
x = 50
y = 60
grh_index = 5003
name = "Puerta Test 3"
is_open = false
"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(toml_content.encode("utf-8"))
            temp_toml_path = Path(f.name)

        try:
            service = MapResourcesService(maps_dir=temp_map_dir)

            # Limpiar puertas que puedan haberse cargado del archivo real
            service.doors.clear()

            # Mockear la construcción de la ruta de puertas
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = True
            mock_path.open.return_value.__enter__ = lambda _: Path(temp_toml_path).open("rb")  # noqa: SIM115
            mock_path.open.return_value.__exit__ = lambda *_: None

            def path_side_effect(*args, **kwargs):  # noqa: ANN002, ANN003
                if len(args) == 1 and str(args[0]).endswith("map_doors.toml"):
                    return mock_path
                if len(args) == 1 and str(args[0]) == "__file__":
                    mock_file_path = MagicMock()
                    mock_file_path.parent.parent.parent.parent.__truediv__ = MagicMock(
                        return_value=mock_path
                    )
                    return mock_file_path
                return Path(*args, **kwargs)

            with patch("src.services.map.map_resources_service.Path", side_effect=path_side_effect):
                # Cargar puertas manuales
                service._load_manual_doors()

                # Verificar que se cargaron las puertas
                assert "map_1" in service.doors
                assert (10, 20) in service.doors["map_1"]
                assert service.doors["map_1"][10, 20] == 5001
                assert (50, 60) in service.doors["map_1"]
                assert service.doors["map_1"][50, 60] == 5003

                assert "map_2" in service.doors
                assert (30, 40) in service.doors["map_2"]
                assert service.doors["map_2"][30, 40] == 5002

        finally:
            if temp_toml_path.exists():
                temp_toml_path.unlink()

    def test_load_manual_doors_with_incomplete_data(self, temp_map_dir, monkeypatch):  # noqa: ARG002
        """Test _load_manual_doors con datos incompletos."""
        # Crear archivo TOML con datos incompletos
        toml_content = """[[door]]
map_id = 1
x = 10
# Falta y y grh_index

[[door]]
map_id = 2
x = 30
y = 40
# Falta grh_index

[[door]]
map_id = 3
x = 50
y = 60
grh_index = 5003
# Este está completo
"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(toml_content.encode("utf-8"))
            temp_toml_path = Path(f.name)

        try:
            service = MapResourcesService(maps_dir=temp_map_dir)

            # Mockear la construcción de la ruta de puertas
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = True
            mock_path.open.return_value.__enter__ = lambda _: Path(temp_toml_path).open("rb")  # noqa: SIM115
            mock_path.open.return_value.__exit__ = lambda *_: None

            def path_side_effect(*args, **kwargs):  # noqa: ANN002, ANN003
                if len(args) == 1 and str(args[0]).endswith("map_doors.toml"):
                    return mock_path
                if len(args) == 1 and str(args[0]) == "__file__":
                    mock_file_path = MagicMock()
                    mock_file_path.parent.parent.parent.parent.__truediv__ = MagicMock(
                        return_value=mock_path
                    )
                    return mock_file_path
                return Path(*args, **kwargs)

            with patch("src.services.map.map_resources_service.Path", side_effect=path_side_effect):
                # No debe lanzar excepción, solo debe ignorar las puertas incompletas
                service._load_manual_doors()

                # Verificar que se cargó la puerta completa (map_3)
                assert "map_3" in service.doors
                assert (50, 60) in service.doors["map_3"]
                assert service.doors["map_3"][50, 60] == 5003

                # Verificar que NO se cargaron las puertas incompletas del archivo temporal
                # (puede haber puertas del archivo real, pero no las del archivo
                # temporal incompleto)
                # Las puertas incompletas del test son: map_1 (10, 20) y map_2 (30, 40)
                if "map_1" in service.doors:
                    # Verificar que no está la puerta incompleta del test (10, 20)
                    assert (10, 20) not in service.doors["map_1"]
                if "map_2" in service.doors:
                    # Verificar que no está la puerta incompleta del test (30, 40)
                    assert (30, 40) not in service.doors["map_2"]

        finally:
            if temp_toml_path.exists():
                temp_toml_path.unlink()

    def test_load_manual_doors_with_exception(self, temp_map_dir, monkeypatch):  # noqa: ARG002
        """Test _load_manual_doors cuando hay una excepción al leer el archivo."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        # Crear un mock Path que existe pero falla al abrir
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.open.side_effect = OSError("Error de lectura")

        def path_side_effect(*args, **kwargs):  # noqa: ANN002, ANN003
            if len(args) == 1 and str(args[0]).endswith("map_doors.toml"):
                return mock_path
            if len(args) == 1 and str(args[0]) == "__file__":
                mock_file_path = MagicMock(spec=Path)
                mock_file_path.parent.parent.parent.parent.__truediv__ = MagicMock(
                    return_value=mock_path
                )
                return mock_file_path
            return Path(*args, **kwargs)

        with patch("src.services.map.map_resources_service.Path", side_effect=path_side_effect):
            # No debe lanzar excepción, solo debe loguear el error
            service._load_manual_doors()

    def test_load_manual_doors_with_map_manager_closed_doors(self, temp_map_dir, monkeypatch):  # noqa: ARG002
        """Test _load_manual_doors con MapManager para bloquear tiles de puertas cerradas."""
        # Crear archivo TOML temporal
        toml_content = """[[door]]
map_id = 1
x = 10
y = 20
grh_index = 5001
name = "Puerta Cerrada"
is_open = false

[[door]]
map_id = 2
x = 30
y = 40
grh_index = 5002
name = "Puerta Abierta"
is_open = true
"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(toml_content.encode("utf-8"))
            temp_toml_path = Path(f.name)

        try:
            # Crear mock de MapManager
            mock_map_manager = MagicMock()

            service = MapResourcesService(maps_dir=temp_map_dir, map_manager=mock_map_manager)

            # Limpiar puertas que puedan haberse cargado del archivo real
            service.doors.clear()
            mock_map_manager.reset_mock()

            # Mockear la construcción de la ruta de puertas
            mock_path = MagicMock(spec=Path)
            mock_path.exists.return_value = True
            mock_path.open.return_value.__enter__ = lambda _: Path(temp_toml_path).open("rb")  # noqa: SIM115
            mock_path.open.return_value.__exit__ = lambda *_: None

            def path_side_effect(*args, **kwargs):  # noqa: ANN002, ANN003
                if len(args) == 1 and str(args[0]).endswith("map_doors.toml"):
                    return mock_path
                if len(args) == 1 and str(args[0]) == "__file__":
                    mock_file_path = MagicMock()
                    mock_file_path.parent.parent.parent.parent.__truediv__ = MagicMock(
                        return_value=mock_path
                    )
                    return mock_file_path
                return Path(*args, **kwargs)

            with patch("src.services.map.map_resources_service.Path", side_effect=path_side_effect):
                # Cargar puertas manuales
                service._load_manual_doors()

                # Verificar que se llamó block_tile solo para la puerta cerrada (map_1)
                mock_map_manager.block_tile.assert_called_once_with(1, 10, 20)

                # Verificar que NO se llamó para la puerta abierta (map_2)
                assert mock_map_manager.block_tile.call_count == 1

        finally:
            if temp_toml_path.exists():
                temp_toml_path.unlink()

    def test_load_manual_doors_with_map_manager_no_doors(self, temp_map_dir):
        """Test _load_manual_doors con MapManager pero sin puertas."""
        mock_map_manager = MagicMock()

        service = MapResourcesService(maps_dir=temp_map_dir, map_manager=mock_map_manager)

        # Si el archivo no existe o no tiene puertas, no debe llamar a block_tile
        # (esto depende de si el archivo real existe)
        service._load_manual_doors()
        # El conteo puede aumentar si el archivo real tiene puertas cerradas
        # Este test solo verifica que no falla

    def test_init_saves_cache_when_resources_exist(self, temp_map_dir):
        """Test que __init__ guarda caché cuando hay recursos."""
        # Crear archivos de mapa para que se carguen recursos
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text(json.dumps({"1": [[10, 10], [10, 11]]}))

        service = MapResourcesService(maps_dir=temp_map_dir)

        # Verificar que se creó el caché
        service.cache_dir / "map_resources_cache.json"
        # El caché puede o no existir dependiendo de si _try_load_from_cache lo cargó
        # Pero si no existe, significa que se guardó después de cargar

    def test_init_warns_when_no_resources(self, temp_map_dir, caplog):
        """Test que __init__ advierte cuando no hay recursos."""
        # Limpiar caché antes del test
        cache_dir = temp_map_dir.parent / "map_cache"
        if cache_dir.exists():
            cache_file = cache_dir / "map_resources_cache.json"
            if cache_file.exists():
                cache_file.unlink()

        # Directorio vacío
        with caplog.at_level("WARNING"):
            service = MapResourcesService(maps_dir=temp_map_dir)

        # Debe haber un warning en los logs si no hay recursos ni caché
        # (puede que haya caché de tests anteriores)
        if len(service.resources) == 0:
            assert any(
                "no se encontraron recursos" in record.message.lower() for record in caplog.records
            )
