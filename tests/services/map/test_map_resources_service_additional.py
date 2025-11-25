"""Tests adicionales para MapResourcesService para mejorar cobertura."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

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


class TestMapResourcesServiceCache:
    """Tests para métodos de caché."""

    def test_read_cache_file_valid(self, temp_map_dir):
        """Test _read_cache_file con archivo válido."""
        cache_path = temp_map_dir / "cache.json"
        cache_data = {"version": 2, "maps": {}}
        with cache_path.open("w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        data = MapResourcesService._read_cache_file(cache_path)
        assert data == cache_data

    def test_read_cache_file_invalid_json(self, temp_map_dir):
        """Test _read_cache_file con JSON inválido."""
        cache_path = temp_map_dir / "cache.json"
        cache_path.write_text("invalid json {")

        with pytest.raises(json.JSONDecodeError):
            MapResourcesService._read_cache_file(cache_path)

    def test_read_cache_file_not_dict(self, temp_map_dir):
        """Test _read_cache_file con JSON que no es dict."""
        cache_path = temp_map_dir / "cache.json"
        with cache_path.open("w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)  # Lista, no dict

        with pytest.raises(json.JSONDecodeError):
            MapResourcesService._read_cache_file(cache_path)

    def test_is_cache_source_valid_matching(self, temp_map_dir):
        """Test _is_cache_source_valid con archivos que coinciden."""
        # Crear archivos
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("[]")
        objects_file = temp_map_dir / "objects_1-50.json"
        objects_file.write_text("[]")

        blocked_files = [blocked_file]
        objects_files = [objects_file]

        # Construir info del caché
        blocked_names, blocked_mtimes = MapResourcesService._build_mtimes(blocked_files)
        objects_names, objects_mtimes = MapResourcesService._build_mtimes(objects_files)

        blocked_info = {"files": blocked_names, "mtimes": blocked_mtimes}
        objects_info = {"files": objects_names, "mtimes": objects_mtimes}

        is_valid = MapResourcesService._is_cache_source_valid(
            blocked_files, objects_files, blocked_info, objects_info
        )
        assert is_valid is True

    def test_is_cache_source_valid_different_files(self, temp_map_dir):
        """Test _is_cache_source_valid con archivos diferentes."""
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("[]")

        blocked_files = [blocked_file]
        objects_files = []

        # Info del caché con archivos diferentes
        blocked_info = {"files": ["blocked_2-50.json"], "mtimes": {}}
        objects_info = {"files": [], "mtimes": {}}

        is_valid = MapResourcesService._is_cache_source_valid(
            blocked_files, objects_files, blocked_info, objects_info
        )
        assert is_valid is False

    def test_is_cache_source_valid_different_mtimes(self, temp_map_dir):
        """Test _is_cache_source_valid con mtimes diferentes."""
        blocked_file = temp_map_dir / "blocked_1-50.json"
        blocked_file.write_text("[]")

        blocked_files = [blocked_file]
        objects_files = []

        blocked_names, _ = MapResourcesService._build_mtimes(blocked_files)
        # Mtimes diferentes
        blocked_info = {"files": blocked_names, "mtimes": {"blocked_1-50.json": 999999}}
        objects_info = {"files": [], "mtimes": {}}

        is_valid = MapResourcesService._is_cache_source_valid(
            blocked_files, objects_files, blocked_info, objects_info
        )
        assert is_valid is False

    def test_build_mtimes_with_oserror(self):
        """Test _build_mtimes cuando stat() falla."""
        # Crear un Path mock que falla en stat()
        mock_path = MagicMock(spec=Path)
        mock_path.name = "test.json"
        mock_path.stat.side_effect = OSError("Permission denied")

        names, mtimes = MapResourcesService._build_mtimes([mock_path])

        assert names == []
        assert mtimes == {}


class TestMapResourcesServiceRebuildCache:
    """Tests para _rebuild_resources_from_cache."""

    def test_rebuild_resources_from_cache_valid(self, temp_map_dir):
        """Test _rebuild_resources_from_cache con datos válidos."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        maps_data = {
            "1": {
                "blocked": [[10, 20], [15, 25]],
                "water": [[5, 5]],
                "trees": [[30, 30]],
                "mines": [[40, 40]],
                "anvils": [[50, 50]],
                "forges": [[60, 60]],
                "signs": [[(70, 70), 1001]],
                "doors": [[(80, 80), 2001]],
            }
        }

        service._rebuild_resources_from_cache(maps_data)

        assert "map_1" in service.resources
        assert (10, 20) in service.resources["map_1"]["blocked"]
        assert (5, 5) in service.resources["map_1"]["water"]
        assert "map_1" in service.signs
        assert (70, 70) in service.signs["map_1"]
        assert "map_1" in service.doors
        assert (80, 80) in service.doors["map_1"]

    def test_rebuild_resources_from_cache_invalid_map_id(self, temp_map_dir):
        """Test _rebuild_resources_from_cache con map_id inválido."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        maps_data = {
            "invalid": {"blocked": [[10, 20]]},  # map_id no es int
            "999": {"blocked": [[10, 20]]},  # Válido
        }

        service._rebuild_resources_from_cache(maps_data)

        # Solo debe cargar el válido
        assert "map_999" in service.resources
        assert "map_invalid" not in service.resources

    def test_rebuild_resources_from_cache_not_dict(self, temp_map_dir):
        """Test _rebuild_resources_from_cache con payload que no es dict."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        maps_data = {
            "1": [1, 2, 3],  # No es dict
            "2": {"blocked": [[10, 20]]},  # Válido
        }

        service._rebuild_resources_from_cache(maps_data)

        # Solo debe cargar el válido
        assert "map_2" in service.resources
        assert "map_1" not in service.resources

    def test_rebuild_resources_from_cache_empty_lists(self, temp_map_dir):
        """Test _rebuild_resources_from_cache con listas vacías."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        maps_data = {
            "1": {
                "blocked": [],
                "water": [],
                "trees": [],
                "mines": [],
                "anvils": [],
                "forges": [],
            }
        }

        service._rebuild_resources_from_cache(maps_data)

        assert "map_1" in service.resources
        assert len(service.resources["map_1"]["blocked"]) == 0


class TestMapResourcesServiceLoadSignsDoors:
    """Tests para _load_signs_from_objects y _load_doors_from_objects."""

    def test_load_signs_from_objects_valid(self, temp_map_dir):
        """Test _load_signs_from_objects con archivo válido."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "sign", "x": 10, "y": 20, "g": 1001}) + "\n")
            f.write(json.dumps({"m": 1, "t": "sign", "x": 15, "y": 25, "g": 1002}) + "\n")

        signs = MapResourcesService._load_signs_from_objects(objects_path, 1)

        assert (10, 20) in signs
        assert signs[10, 20] == 1001
        assert (15, 25) in signs
        assert signs[15, 25] == 1002

    def test_load_signs_from_objects_wrong_map(self, temp_map_dir):
        """Test _load_signs_from_objects con mapa incorrecto."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 2, "t": "sign", "x": 10, "y": 20, "g": 1001}) + "\n")

        signs = MapResourcesService._load_signs_from_objects(objects_path, 1)

        assert len(signs) == 0

    def test_load_signs_from_objects_wrong_type(self, temp_map_dir):
        """Test _load_signs_from_objects con tipo incorrecto."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "tree", "x": 10, "y": 20, "g": 1001}) + "\n")

        signs = MapResourcesService._load_signs_from_objects(objects_path, 1)

        assert len(signs) == 0

    def test_load_signs_from_objects_invalid_json(self, temp_map_dir):
        """Test _load_signs_from_objects con JSON inválido."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write("invalid json {}\n")
            f.write(json.dumps({"m": 1, "t": "sign", "x": 10, "y": 20, "g": 1001}) + "\n")

        signs = MapResourcesService._load_signs_from_objects(objects_path, 1)

        # Debe ignorar la línea inválida y cargar la válida
        assert (10, 20) in signs

    def test_load_signs_from_objects_nonexistent_file(self):
        """Test _load_signs_from_objects con archivo inexistente."""
        nonexistent_path = Path("/nonexistent/objects.json")
        signs = MapResourcesService._load_signs_from_objects(nonexistent_path, 1)

        assert len(signs) == 0

    def test_load_doors_from_objects_valid(self, temp_map_dir):
        """Test _load_doors_from_objects con archivo válido."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "door", "x": 10, "y": 20, "g": 2001}) + "\n")
            f.write(json.dumps({"m": 1, "t": "door", "x": 15, "y": 25, "g": 2002}) + "\n")

        doors = MapResourcesService._load_doors_from_objects(objects_path, 1)

        assert (10, 20) in doors
        assert doors[10, 20] == 2001
        assert (15, 25) in doors
        assert doors[15, 25] == 2002

    def test_load_doors_from_objects_wrong_map(self, temp_map_dir):
        """Test _load_doors_from_objects con mapa incorrecto."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 2, "t": "door", "x": 10, "y": 20, "g": 2001}) + "\n")

        doors = MapResourcesService._load_doors_from_objects(objects_path, 1)

        assert len(doors) == 0

    def test_load_doors_from_objects_invalid_coords(self, temp_map_dir):
        """Test _load_doors_from_objects con coordenadas inválidas."""
        objects_path = temp_map_dir / "objects_1-50.json"
        with objects_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"m": 1, "t": "door", "x": "invalid", "y": 20, "g": 2001}) + "\n")
            f.write(json.dumps({"m": 1, "t": "door", "x": 10, "y": 20, "g": 2001}) + "\n")

        doors = MapResourcesService._load_doors_from_objects(objects_path, 1)

        # Solo debe cargar la válida
        assert (10, 20) in doors
        assert len(doors) == 1


class TestMapResourcesServiceGetters:
    """Tests para métodos getter."""

    def test_get_door_at_existing(self, temp_map_dir):
        """Test get_door_at con puerta existente."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        service.doors["map_1"] = {(10, 20): 2001}

        grh = service.get_door_at(1, 10, 20)
        assert grh == 2001

    def test_get_door_at_nonexistent_map(self, temp_map_dir):
        """Test get_door_at con mapa inexistente."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        grh = service.get_door_at(999, 10, 20)
        assert grh is None

    def test_get_door_at_nonexistent_position(self, temp_map_dir):
        """Test get_door_at con posición inexistente."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        service.doors["map_1"] = {(10, 20): 2001}

        grh = service.get_door_at(1, 15, 25)
        assert grh is None

    def test_get_sign_at_existing(self, temp_map_dir):
        """Test get_sign_at con cartel existente."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        service.signs["map_1"] = {(10, 20): 1001}

        grh = service.get_sign_at(1, 10, 20)
        assert grh == 1001

    def test_get_sign_at_nonexistent_map(self, temp_map_dir):
        """Test get_sign_at con mapa inexistente."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        grh = service.get_sign_at(999, 10, 20)
        assert grh is None

    def test_get_sign_at_nonexistent_position(self, temp_map_dir):
        """Test get_sign_at con posición inexistente."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        service.signs["map_1"] = {(10, 20): 1001}

        grh = service.get_sign_at(1, 15, 25)
        assert grh is None

    def test_has_anvil_existing(self, temp_map_dir):
        """Test has_anvil con yunque existente."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        service.resources["map_1"] = {"anvils": {(10, 20)}}

        assert service.has_anvil(1, 10, 20) is True
        assert service.has_anvil(1, 15, 25) is False

    def test_has_forge_existing(self, temp_map_dir):
        """Test has_forge con forja existente."""
        service = MapResourcesService(maps_dir=temp_map_dir)
        service.resources["map_1"] = {"forges": {(10, 20)}}

        assert service.has_forge(1, 10, 20) is True
        assert service.has_forge(1, 15, 25) is False
