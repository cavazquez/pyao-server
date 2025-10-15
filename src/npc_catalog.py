"""Catálogo de NPCs cargado desde npcs.toml."""

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)


class NPCCatalog:
    """Gestiona el catálogo de NPCs desde el archivo data/npcs.toml.

    El catálogo contiene las plantillas de NPCs que se pueden instanciar
    en el mundo. Cada NPC tiene un ID único y propiedades base.
    """

    def __init__(self, data_path: str = "data/npcs.toml") -> None:
        """Inicializa el catálogo de NPCs.

        Args:
            data_path: Ruta al archivo npcs.toml.
        """
        self._npcs: dict[int, dict[str, object]] = {}
        self._data_path = data_path
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Carga el catálogo de NPCs desde el archivo TOML."""
        try:
            path = Path(self._data_path)
            if not path.exists():
                logger.warning("Archivo de NPCs no encontrado: %s", self._data_path)
                return

            with path.open("rb") as f:
                data = tomllib.load(f)

            if "npc" not in data:
                logger.warning("No se encontró la sección [npc] en %s", self._data_path)
                return

            for npc_data in data["npc"]:
                npc_id = npc_data.get("id")
                if npc_id is None:
                    logger.warning("NPC sin ID encontrado, ignorando: %s", npc_data)
                    continue

                self._npcs[npc_id] = npc_data
                logger.debug("NPC cargado: %d - %s", npc_id, npc_data.get("nombre", "Sin nombre"))

            logger.info("Catálogo de NPCs cargado: %d NPCs", len(self._npcs))

        except Exception:
            logger.exception("Error al cargar catálogo de NPCs desde %s", self._data_path)

    def get_npc_data(self, npc_id: int) -> dict[str, object] | None:
        """Obtiene los datos de un NPC por su ID.

        Args:
            npc_id: ID del NPC en el catálogo.

        Returns:
            Diccionario con los datos del NPC o None si no existe.
        """
        return self._npcs.get(npc_id)

    def get_all_npc_ids(self) -> list[int]:
        """Obtiene la lista de todos los IDs de NPCs en el catálogo.

        Returns:
            Lista de IDs de NPCs.
        """
        return list(self._npcs.keys())

    def npc_exists(self, npc_id: int) -> bool:
        """Verifica si un NPC existe en el catálogo.

        Args:
            npc_id: ID del NPC.

        Returns:
            True si el NPC existe, False en caso contrario.
        """
        return npc_id in self._npcs
