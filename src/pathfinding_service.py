"""Servicio de pathfinding para NPCs usando A*."""

import heapq
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.map_manager import MapManager

logger = logging.getLogger(__name__)


class PathfindingService:
    """Servicio para calcular rutas óptimas usando A* (4 direcciones)."""

    def __init__(self, map_manager: MapManager) -> None:
        """Inicializa el servicio de pathfinding.

        Args:
            map_manager: Gestor de mapas para validar colisiones.
        """
        self.map_manager = map_manager

        # Direcciones posibles (4 direcciones, SIN diagonal): (dx, dy, heading)
        self.directions = [
            (0, -1, 1),  # Norte
            (1, 0, 2),  # Este
            (0, 1, 3),  # Sur
            (-1, 0, 4),  # Oeste
        ]

    def get_next_step(
        self,
        map_id: int,
        start_x: int,
        start_y: int,
        target_x: int,
        target_y: int,
        max_depth: int = 20,
    ) -> tuple[int, int, int] | None:
        """Calcula el siguiente paso hacia el objetivo usando A*.

        Args:
            map_id: ID del mapa.
            start_x: Posición X inicial.
            start_y: Posición Y inicial.
            target_x: Posición X objetivo.
            target_y: Posición Y objetivo.
            max_depth: Profundidad máxima de búsqueda (evita cálculos excesivos).

        Returns:
            Tupla (next_x, next_y, heading) con el siguiente paso, o None si no hay camino.
        """
        # Si ya estamos en el objetivo, no hay que moverse
        if start_x == target_x and start_y == target_y:
            return None

        # Si el objetivo está bloqueado, no tiene sentido buscar camino
        if not self.map_manager.can_move_to(map_id, target_x, target_y):
            return None

        # Ejecutar A*
        path = self._astar(map_id, start_x, start_y, target_x, target_y, max_depth)

        # Si no hay camino, retornar None
        if not path or len(path) < 2:  # noqa: PLR2004
            return None

        # Retornar el primer paso de la ruta (después del punto inicial)
        next_pos = path[1]
        next_x, next_y = next_pos

        # Calcular heading basado en la dirección
        dx = next_x - start_x
        dy = next_y - start_y

        # Determinar heading (1=Norte, 2=Este, 3=Sur, 4=Oeste)
        if dy == -1:
            heading = 1  # Norte
        elif dx == 1:
            heading = 2  # Este
        elif dy == 1:
            heading = 3  # Sur
        else:  # dx == -1
            heading = 4  # Oeste

        return next_x, next_y, heading

    def _astar(
        self,
        map_id: int,
        start_x: int,
        start_y: int,
        target_x: int,
        target_y: int,
        max_depth: int,
    ) -> list[tuple[int, int]] | None:
        """Implementación del algoritmo A*.

        Args:
            map_id: ID del mapa.
            start_x: Posición X inicial.
            start_y: Posición Y inicial.
            target_x: Posición X objetivo.
            target_y: Posición Y objetivo.
            max_depth: Profundidad máxima de búsqueda.

        Returns:
            Lista de posiciones (x, y) desde start hasta target, o None si no hay camino.
        """
        # Priority queue: (f_score, counter, (x, y))
        # counter es para desempatar cuando f_score es igual
        counter = 0
        open_set: list[tuple[float, int, tuple[int, int]]] = []
        heapq.heappush(open_set, (0, counter, (start_x, start_y)))

        # Diccionario para rastrear de dónde vinimos
        came_from: dict[tuple[int, int], tuple[int, int]] = {}

        # g_score: costo desde start hasta el nodo
        g_score: dict[tuple[int, int], float] = {(start_x, start_y): 0}

        # f_score es el costo estimado total
        f_score: dict[tuple[int, int], float] = {
            (start_x, start_y): self._heuristic(start_x, start_y, target_x, target_y)
        }

        # Conjunto de nodos visitados
        closed_set: set[tuple[int, int]] = set()

        nodes_explored = 0

        while open_set:
            # Obtener nodo con menor f_score
            _, _, current = heapq.heappop(open_set)

            # Si llegamos al objetivo, reconstruir camino
            if current == (target_x, target_y):
                return self._reconstruct_path(came_from, current)

            # Marcar como visitado
            closed_set.add(current)
            nodes_explored += 1

            # Límite de profundidad (evitar búsquedas infinitas)
            if nodes_explored > max_depth:
                logger.debug(
                    "Pathfinding: límite de profundidad alcanzado (%d nodos)", max_depth
                )
                return None

            # Explorar vecinos (4 direcciones)
            current_x, current_y = current
            for dx, dy, _ in self.directions:
                neighbor_x = current_x + dx
                neighbor_y = current_y + dy
                neighbor = (neighbor_x, neighbor_y)

                # Si ya fue visitado, saltear
                if neighbor in closed_set:
                    continue

                # Verificar si es un tile válido (no bloqueado, no ocupado)
                if not self.map_manager.can_move_to(map_id, neighbor_x, neighbor_y):
                    continue

                # Calcular g_score tentativo
                tentative_g = g_score[current] + 1  # Costo 1 por cada movimiento

                # Si encontramos un camino mejor, actualizar
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(
                        neighbor_x, neighbor_y, target_x, target_y
                    )

                    # Agregar a open_set si no está
                    counter += 1
                    heapq.heappush(open_set, (f_score[neighbor], counter, neighbor))

        # No se encontró camino
        logger.debug(
            "Pathfinding: no se encontró camino desde (%d,%d) a (%d,%d)",
            start_x,
            start_y,
            target_x,
            target_y,
        )
        return None

    @staticmethod
    def _heuristic(x1: int, y1: int, x2: int, y2: int) -> float:
        """Calcula la distancia heurística (Manhattan).

        Args:
            x1: Posición X inicial.
            y1: Posición Y inicial.
            x2: Posición X objetivo.
            y2: Posición Y objetivo.

        Returns:
            Distancia Manhattan.
        """
        return abs(x1 - x2) + abs(y1 - y2)

    @staticmethod
    def _reconstruct_path(
        came_from: dict[tuple[int, int], tuple[int, int]], current: tuple[int, int]
    ) -> list[tuple[int, int]]:
        """Reconstruye el camino desde start hasta current.

        Args:
            came_from: Diccionario de padres.
            current: Nodo final.

        Returns:
            Lista de posiciones desde start hasta current.
        """
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path
