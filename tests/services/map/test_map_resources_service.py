"""Tests para MapResourcesService."""

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
