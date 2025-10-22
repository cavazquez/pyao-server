"""Servicio para manejar transiciones entre mapas."""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MapTransition:
    """Transición entre mapas.

    Attributes:
        from_map: ID del mapa actual.
        edge: Borde del mapa ("north", "south", "east", "west").
        to_map: ID del mapa destino.
        to_x: Coordenada X de entrada en el nuevo mapa.
        to_y: Coordenada Y de entrada en el nuevo mapa.
    """

    from_map: int
    edge: str
    to_map: int
    to_x: int
    to_y: int


class MapTransitionService:
    """Servicio que maneja las transiciones entre mapas."""

    def __init__(self, transitions_path: str = "data/map_transitions.toml") -> None:
        """Inicializa el servicio de transiciones.

        Args:
            transitions_path: Ruta al archivo de transiciones.
        """
        self._transitions: dict[tuple[int, str], MapTransition] = {}
        self._load_transitions(transitions_path)

    def _load_transitions(self, path: str) -> None:
        """Carga las transiciones desde el archivo TOML.

        Args:
            path: Ruta al archivo TOML.
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                logger.warning("Archivo de transiciones no encontrado: %s", path)
                return

            with file_path.open("rb") as f:
                data = tomllib.load(f)

            for trans_data in data.get("transition", []):
                transition = MapTransition(
                    from_map=trans_data["from_map"],
                    edge=trans_data["edge"],
                    to_map=trans_data["to_map"],
                    to_x=trans_data["to_x"],
                    to_y=trans_data["to_y"],
                )

                key = (transition.from_map, transition.edge)
                self._transitions[key] = transition

                logger.debug(
                    "Transición cargada: Mapa %d (%s) -> Mapa %d (%d, %d)",
                    transition.from_map,
                    transition.edge,
                    transition.to_map,
                    transition.to_x,
                    transition.to_y,
                )

            logger.info("Transiciones de mapa cargadas: %d", len(self._transitions))

        except Exception:
            logger.exception("Error al cargar transiciones desde %s", path)

    def get_transition(self, from_map: int, edge: str) -> MapTransition | None:
        """Obtiene la transición para un mapa y borde específicos.

        Args:
            from_map: ID del mapa actual.
            edge: Borde del mapa ("north", "south", "east", "west").

        Returns:
            MapTransition si existe, None si no hay transición configurada.
        """
        return self._transitions.get((from_map, edge))

    def has_transition(self, from_map: int, edge: str) -> bool:
        """Verifica si existe una transición para un mapa y borde.

        Args:
            from_map: ID del mapa actual.
            edge: Borde del mapa.

        Returns:
            True si existe transición, False si no.
        """
        return (from_map, edge) in self._transitions

    def get_all_transitions_for_map(self, map_id: int) -> list[MapTransition]:
        """Obtiene todas las transiciones de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Lista de transiciones del mapa.
        """
        return [
            transition
            for (from_map, _), transition in self._transitions.items()
            if from_map == map_id
        ]
