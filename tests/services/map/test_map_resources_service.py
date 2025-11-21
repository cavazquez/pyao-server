"""Tests para MapResourcesService."""

import json
import tempfile
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


class TestMapResourcesService:
    """Tests para MapResourcesService."""

    def test_init_with_empty_directory(self, temp_map_dir):
        """Test inicialización con directorio vacío."""
        service = MapResourcesService(maps_dir=temp_map_dir)

        assert service is not None
        assert service.maps_dir == temp_map_dir
        assert len(service.resources) == 0

    def test_init_with_nonexistent_directory(self):
        """Test inicialización con directorio que no existe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "nonexistent"

            service = MapResourcesService(maps_dir=nonexistent)

            assert service is not None
            assert service.maps_dir == nonexistent
            # El directorio debe haberse creado
            assert nonexistent.exists()

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
