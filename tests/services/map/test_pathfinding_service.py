"""Tests para PathfindingService (A* pathfinding)."""

from unittest.mock import MagicMock

import pytest

from src.services.map.pathfinding_service import PathfindingService


@pytest.fixture
def mock_map_manager():
    """Mock de MapManager."""
    manager = MagicMock()
    # Por defecto, todos los tiles son transitables
    manager.can_move_to.return_value = True
    return manager


class TestPathfindingService:
    """Tests para PathfindingService."""

    def test_init(self, mock_map_manager):
        """Test inicialización del servicio."""
        service = PathfindingService(mock_map_manager)

        assert service is not None
        assert service.map_manager == mock_map_manager
        assert len(service.directions) == 4  # 4 direcciones (sin diagonal)

    def test_get_next_step_already_at_target(self, mock_map_manager):
        """Test cuando ya estamos en el objetivo."""
        service = PathfindingService(mock_map_manager)

        # Mismo punto de inicio y objetivo
        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=50, target_y=50)

        assert result is None

    def test_get_next_step_target_blocked(self, mock_map_manager):
        """Test cuando el objetivo está bloqueado."""
        service = PathfindingService(mock_map_manager)

        # El objetivo (60, 60) está bloqueado
        def can_move_to_mock(_map_id, x, y):
            return not (x == 60 and y == 60)

        mock_map_manager.can_move_to.side_effect = can_move_to_mock

        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=60, target_y=60)

        assert result is None

    def test_get_next_step_straight_path_north(self, mock_map_manager):
        """Test camino recto hacia el norte."""
        service = PathfindingService(mock_map_manager)

        # Ir de (50, 50) a (50, 45) - 5 tiles al norte
        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=50, target_y=45)

        assert result is not None
        next_x, next_y, heading = result
        assert next_x == 50
        assert next_y == 49  # Un paso al norte
        assert heading == 1  # Norte

    def test_get_next_step_straight_path_east(self, mock_map_manager):
        """Test camino recto hacia el este."""
        service = PathfindingService(mock_map_manager)

        # Ir de (50, 50) a (55, 50) - 5 tiles al este
        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=55, target_y=50)

        assert result is not None
        next_x, next_y, heading = result
        assert next_x == 51  # Un paso al este
        assert next_y == 50
        assert heading == 2  # Este

    def test_get_next_step_straight_path_south(self, mock_map_manager):
        """Test camino recto hacia el sur."""
        service = PathfindingService(mock_map_manager)

        # Ir de (50, 50) a (50, 55) - 5 tiles al sur
        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=50, target_y=55)

        assert result is not None
        next_x, next_y, heading = result
        assert next_x == 50
        assert next_y == 51  # Un paso al sur
        assert heading == 3  # Sur

    def test_get_next_step_straight_path_west(self, mock_map_manager):
        """Test camino recto hacia el oeste."""
        service = PathfindingService(mock_map_manager)

        # Ir de (50, 50) a (45, 50) - 5 tiles al oeste
        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=45, target_y=50)

        assert result is not None
        next_x, next_y, heading = result
        assert next_x == 49  # Un paso al oeste
        assert next_y == 50
        assert heading == 4  # Oeste

    def test_get_next_step_with_obstacle(self, mock_map_manager):
        """Test pathfinding rodeando un obstáculo."""
        service = PathfindingService(mock_map_manager)

        # Crear un muro vertical en x=51
        def can_move_to_mock(map_id, x, y):  # noqa: ARG001
            # Muro en x=51, y entre 48 y 52
            return not (x == 51 and 48 <= y <= 52)

        mock_map_manager.can_move_to.side_effect = can_move_to_mock

        # Ir de (50, 50) a (52, 50) - debe rodear el muro
        result = service.get_next_step(
            map_id=1, start_x=50, start_y=50, target_x=52, target_y=50, max_depth=50
        )

        assert result is not None
        next_x, next_y, _heading = result

        # Debe moverse hacia arriba o abajo para rodear
        assert next_x == 50
        assert next_y in {49, 51}  # Norte o Sur

    def test_get_next_step_no_path(self, mock_map_manager):
        """Test cuando no hay camino posible."""
        service = PathfindingService(mock_map_manager)

        # Crear un muro que rodea completamente el objetivo
        def can_move_to_mock(map_id, x, y):  # noqa: ARG001
            # Objetivo en (55, 55), rodeado por muros
            if x == 55 and y == 55:
                return True  # El objetivo es válido
            # Muros alrededor
            return not (54 <= x <= 56 and 54 <= y <= 56)

        mock_map_manager.can_move_to.side_effect = can_move_to_mock

        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=55, target_y=55)

        # No debe encontrar camino
        assert result is None

    def test_get_next_step_max_depth_limit(self, mock_map_manager):
        """Test que respeta el límite de profundidad."""
        service = PathfindingService(mock_map_manager)

        # Objetivo muy lejano con max_depth bajo
        result = service.get_next_step(
            map_id=1, start_x=50, start_y=50, target_x=100, target_y=100, max_depth=5
        )

        # Debe retornar None porque excede max_depth
        assert result is None

    def test_heuristic_manhattan_distance(self):
        """Test que la heurística calcula distancia Manhattan correctamente."""
        # Distancia Manhattan entre (0, 0) y (3, 4) = 3 + 4 = 7
        distance = PathfindingService._heuristic(0, 0, 3, 4)
        assert distance == 7

        # Distancia Manhattan entre (10, 10) y (15, 12) = 5 + 2 = 7
        distance = PathfindingService._heuristic(10, 10, 15, 12)
        assert distance == 7

        # Distancia Manhattan entre (5, 5) y (5, 5) = 0
        distance = PathfindingService._heuristic(5, 5, 5, 5)
        assert distance == 0

    def test_reconstruct_path(self):
        """Test reconstrucción de camino."""
        came_from = {
            (1, 1): (0, 0),
            (2, 1): (1, 1),
            (3, 1): (2, 1),
        }

        path = PathfindingService._reconstruct_path(came_from, (3, 1))

        assert path == [(0, 0), (1, 1), (2, 1), (3, 1)]

    def test_reconstruct_path_single_node(self):
        """Test reconstrucción de camino con un solo nodo."""
        came_from = {}

        path = PathfindingService._reconstruct_path(came_from, (5, 5))

        assert path == [(5, 5)]

    def test_get_next_step_one_tile_away(self, mock_map_manager):
        """Test cuando el objetivo está a 1 tile de distancia."""
        service = PathfindingService(mock_map_manager)

        # Objetivo a 1 tile al norte
        result = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=50, target_y=49)

        assert result is not None
        next_x, next_y, heading = result
        assert next_x == 50
        assert next_y == 49
        assert heading == 1  # Norte

    def test_get_next_step_diagonal_target(self, mock_map_manager):
        """Test cuando el objetivo está en diagonal (debe usar 4 direcciones)."""
        service = PathfindingService(mock_map_manager)

        # Objetivo en diagonal (55, 55) desde (50, 50)
        result = service.get_next_step(
            map_id=1, start_x=50, start_y=50, target_x=55, target_y=55, max_depth=50
        )

        assert result is not None
        next_x, next_y, _heading = result

        # Debe moverse en una de las 4 direcciones (no diagonal)
        # Puede ir al este (51, 50) o al sur (50, 51)
        assert (next_x == 51 and next_y == 50) or (next_x == 50 and next_y == 51)

    def test_directions_are_four_only(self, mock_map_manager):
        """Test que solo hay 4 direcciones (sin diagonal)."""
        service = PathfindingService(mock_map_manager)

        assert len(service.directions) == 4

        # Verificar que son las 4 direcciones cardinales
        directions_set = {(dx, dy) for dx, dy, _ in service.directions}
        expected = {(0, -1), (1, 0), (0, 1), (-1, 0)}  # Norte, Este, Sur, Oeste

        assert directions_set == expected

    def test_get_next_step_with_complex_maze(self, mock_map_manager):
        """Test pathfinding en un laberinto complejo."""
        service = PathfindingService(mock_map_manager)

        # Crear un laberinto simple
        blocked_tiles = {
            (51, 49),
            (51, 50),
            (51, 51),  # Muro vertical
            (52, 51),
            (53, 51),  # Muro horizontal
        }

        def can_move_to_mock(map_id, x, y):  # noqa: ARG001
            return (x, y) not in blocked_tiles

        mock_map_manager.can_move_to.side_effect = can_move_to_mock

        # Ir de (50, 50) a (54, 50) - debe encontrar camino
        result = service.get_next_step(
            map_id=1, start_x=50, start_y=50, target_x=54, target_y=50, max_depth=50
        )

        # Debe encontrar algún camino
        assert result is not None

    def test_get_next_step_different_map_ids(self, mock_map_manager):
        """Test que funciona con diferentes IDs de mapa."""
        service = PathfindingService(mock_map_manager)

        # Mapa 1
        result1 = service.get_next_step(map_id=1, start_x=50, start_y=50, target_x=50, target_y=45)
        assert result1 is not None

        # Mapa 2
        result2 = service.get_next_step(map_id=2, start_x=50, start_y=50, target_x=50, target_y=45)
        assert result2 is not None

        # Mapa 999
        result3 = service.get_next_step(
            map_id=999, start_x=50, start_y=50, target_x=50, target_y=45
        )
        assert result3 is not None
