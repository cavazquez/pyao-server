"""Tests para MapTransitionService."""

import tempfile
from pathlib import Path

import pytest

from src.services.map.map_transition_service import MapTransition, MapTransitionService


@pytest.fixture
def temp_transitions_file():
    """Crea un archivo temporal de transiciones.

    Yields:
        str: Path al archivo temporal de transiciones.
    """
    with tempfile.NamedTemporaryFile(encoding="utf-8", mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[[transition]]
from_map = 1
edge = "north"
to_map = 2
to_x = 50
to_y = 99

[[transition]]
from_map = 1
edge = "south"
to_map = 3
to_x = 50
to_y = 2

[[transition]]
from_map = 1
edge = "east"
to_map = 4
to_x = 2
to_y = 50

[[transition]]
from_map = 1
edge = "west"
to_map = 5
to_x = 99
to_y = 50

[[transition]]
from_map = 2
edge = "south"
to_map = 1
to_x = 50
to_y = 2
""")
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink()


class TestMapTransition:
    """Tests para MapTransition dataclass."""

    def test_map_transition_creation(self):
        """Test creación de MapTransition."""
        transition = MapTransition(from_map=1, edge="north", to_map=2, to_x=50, to_y=99)

        assert transition.from_map == 1
        assert transition.edge == "north"
        assert transition.to_map == 2
        assert transition.to_x == 50
        assert transition.to_y == 99


class TestMapTransitionService:
    """Tests para MapTransitionService."""

    def test_init_with_nonexistent_file(self):
        """Test inicialización con archivo que no existe."""
        service = MapTransitionService(transitions_path="nonexistent.toml")

        assert service is not None
        assert len(service._transitions) == 0

    def test_init_with_valid_file(self, temp_transitions_file):
        """Test inicialización con archivo válido."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        assert service is not None
        # Debe haber cargado 5 transiciones
        assert len(service._transitions) == 5

    def test_get_transition_exists(self, temp_transitions_file):
        """Test obtener transición que existe."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        transition = service.get_transition(1, "north")

        assert transition is not None
        assert transition.from_map == 1
        assert transition.edge == "north"
        assert transition.to_map == 2
        assert transition.to_x == 50
        assert transition.to_y == 99

    def test_get_transition_not_exists(self, temp_transitions_file):
        """Test obtener transición que no existe."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        transition = service.get_transition(999, "north")

        assert transition is None

    def test_has_transition_exists(self, temp_transitions_file):
        """Test verificar si existe transición."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        assert service.has_transition(1, "north") is True
        assert service.has_transition(1, "south") is True
        assert service.has_transition(1, "east") is True
        assert service.has_transition(1, "west") is True

    def test_has_transition_not_exists(self, temp_transitions_file):
        """Test verificar transición que no existe."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        assert service.has_transition(999, "north") is False
        assert service.has_transition(1, "invalid") is False

    def test_get_all_transitions_for_map(self, temp_transitions_file):
        """Test obtener todas las transiciones de un mapa."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        transitions = service.get_all_transitions_for_map(1)

        assert len(transitions) == 4  # Mapa 1 tiene 4 transiciones
        edges = {t.edge for t in transitions}
        assert edges == {"north", "south", "east", "west"}

    def test_get_all_transitions_for_map_no_transitions(self, temp_transitions_file):
        """Test obtener transiciones de mapa sin transiciones."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        transitions = service.get_all_transitions_for_map(999)

        assert len(transitions) == 0

    def test_multiple_transitions_same_map(self, temp_transitions_file):
        """Test múltiples transiciones desde el mismo mapa."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        north = service.get_transition(1, "north")
        south = service.get_transition(1, "south")
        east = service.get_transition(1, "east")
        west = service.get_transition(1, "west")

        assert north is not None
        assert south is not None
        assert east is not None
        assert west is not None

        # Verificar que van a mapas diferentes
        assert north.to_map == 2
        assert south.to_map == 3
        assert east.to_map == 4
        assert west.to_map == 5

    def test_bidirectional_transitions(self, temp_transitions_file):
        """Test transiciones bidireccionales."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        # Mapa 1 norte -> Mapa 2
        forward = service.get_transition(1, "north")
        assert forward is not None
        assert forward.to_map == 2

        # Mapa 2 sur -> Mapa 1 (vuelta)
        backward = service.get_transition(2, "south")
        assert backward is not None
        assert backward.to_map == 1

    def test_transition_coordinates(self, temp_transitions_file):
        """Test que las coordenadas de entrada son correctas."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        # Norte: debería entrar por el sur del nuevo mapa (y alto)
        north = service.get_transition(1, "north")
        assert north.to_y == 99

        # Sur: debería entrar por el norte del nuevo mapa (y bajo)
        south = service.get_transition(1, "south")
        assert south.to_y == 2

        # Este: debería entrar por el oeste del nuevo mapa (x bajo)
        east = service.get_transition(1, "east")
        assert east.to_x == 2

        # Oeste: debería entrar por el este del nuevo mapa (x alto)
        west = service.get_transition(1, "west")
        assert west.to_x == 99

    def test_empty_toml_file(self):
        """Test con archivo TOML vacío."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("")  # Archivo vacío
            temp_path = f.name

        try:
            service = MapTransitionService(transitions_path=temp_path)

            assert len(service._transitions) == 0
        finally:
            Path(temp_path).unlink()

    def test_malformed_toml_file(self):
        """Test con archivo TOML malformado."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("{invalid toml")
            temp_path = f.name

        try:
            service = MapTransitionService(transitions_path=temp_path)

            # No debe lanzar excepción, debe manejar el error
            assert len(service._transitions) == 0
        finally:
            Path(temp_path).unlink()

    def test_toml_missing_fields(self):
        """Test con transición que le faltan campos."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("""
[[transition]]
from_map = 1
edge = "north"
# Falta to_map, to_x, to_y
""")
            temp_path = f.name

        try:
            service = MapTransitionService(transitions_path=temp_path)

            # Debe manejar el error y no cargar la transición inválida
            assert len(service._transitions) == 0
        finally:
            Path(temp_path).unlink()

    def test_edge_case_sensitivity(self, temp_transitions_file):
        """Test que los edges son case-sensitive."""
        service = MapTransitionService(transitions_path=temp_transitions_file)

        # "north" existe
        assert service.has_transition(1, "north") is True

        # "North" no existe (case-sensitive)
        assert service.has_transition(1, "North") is False
        assert service.has_transition(1, "NORTH") is False

    def test_default_transitions_path(self):
        """Test que el path por defecto es correcto."""
        service = MapTransitionService()

        # No debe lanzar excepción
        assert service is not None

    def test_transition_overwrite(self):
        """Test que transiciones duplicadas se sobrescriben."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".toml", delete=False
        ) as f:
            f.write("""
[[transition]]
from_map = 1
edge = "north"
to_map = 2
to_x = 50
to_y = 99

[[transition]]
from_map = 1
edge = "north"
to_map = 3
to_x = 60
to_y = 88
""")
            temp_path = f.name

        try:
            service = MapTransitionService(transitions_path=temp_path)

            # Solo debe haber 1 transición (la última sobrescribe)
            assert len(service._transitions) == 1

            transition = service.get_transition(1, "north")
            # Debe tener los valores de la segunda definición
            assert transition.to_map == 3
            assert transition.to_x == 60
            assert transition.to_y == 88
        finally:
            Path(temp_path).unlink()

    def test_many_transitions(self):
        """Test con muchas transiciones."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8", mode="w", suffix=".toml", delete=False
        ) as f:
            # Crear 100 transiciones
            for i in range(1, 101):
                f.write(f"""
[[transition]]
from_map = {i}
edge = "north"
to_map = {i + 1}
to_x = 50
to_y = 99
""")
            temp_path = f.name

        try:
            service = MapTransitionService(transitions_path=temp_path)

            assert len(service._transitions) == 100

            # Verificar algunas transiciones
            assert service.has_transition(1, "north") is True
            assert service.has_transition(50, "north") is True
            assert service.has_transition(100, "north") is True
        finally:
            Path(temp_path).unlink()
