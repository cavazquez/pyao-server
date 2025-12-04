"""Catálogo de NPCs cargado desde archivos TOML."""

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)


class NPCCatalog:
    """Gestiona el catálogo de NPCs desde archivos TOML.

    El catálogo contiene las plantillas de NPCs que se pueden instanciar
    en el mundo. Cada NPC tiene un ID único y propiedades base.

    Carga NPCs desde múltiples archivos:
    - npcs/hostiles.toml: Criaturas agresivas
    - npcs/friendly.toml: NPCs de servicios
    """

    def __init__(
        self,
        hostile_path: str = "data/npcs/hostiles.toml",
        friendly_path: str = "data/npcs/friendly.toml",
    ) -> None:
        """Inicializa el catálogo de NPCs.

        Args:
            hostile_path: Ruta al archivo de NPCs hostiles.
            friendly_path: Ruta al archivo de NPCs amigables.
        """
        self._npcs: dict[int, dict[str, object]] = {}
        self._hostile_path = hostile_path
        self._friendly_path = friendly_path
        self._load_catalog()

    def _load_file(self, file_path: str, file_type: str) -> None:
        """Carga NPCs desde un archivo TOML.

        Args:
            file_path: Ruta al archivo.
            file_type: Tipo de archivo para logging (hostile/friendly/legacy).
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.debug("Archivo de NPCs %s no encontrado: %s", file_type, file_path)
                return

            with path.open("rb") as f:
                data = tomllib.load(f)

            # Soportar múltiples formatos:
            # 1. [[npc]] - formato legacy/friendly
            # 2. [[npcs_hostiles.npcs]] - formato hostiles regenerado
            # 3. [[npcs_complete.npcs]] - formato complete regenerado
            npcs_list = None
            if "npc" in data:
                npcs_list = data["npc"]
            elif "npcs_hostiles" in data and "npcs" in data["npcs_hostiles"]:
                npcs_list = data["npcs_hostiles"]["npcs"]
            elif "npcs_complete" in data and "npcs" in data["npcs_complete"]:
                npcs_list = data["npcs_complete"]["npcs"]
            elif "npcs_traders" in data and "npcs" in data["npcs_traders"]:
                npcs_list = data["npcs_traders"]["npcs"]

            if npcs_list is None:
                logger.warning("No se encontró sección de NPCs válida en %s", file_path)
                return

            count = 0
            for npc_data in npcs_list:
                npc_id = npc_data.get("id")
                if npc_id is None:
                    logger.warning("NPC sin ID encontrado, ignorando: %s", npc_data)
                    continue

                self._npcs[npc_id] = npc_data
                logger.debug(
                    "NPC cargado: %d - %s",
                    npc_id,
                    npc_data.get("name", npc_data.get("nombre", "Sin nombre")),
                )
                count += 1

            logger.info("NPCs %s cargados: %d NPCs desde %s", file_type, count, file_path)

        except Exception:
            logger.exception("Error al cargar NPCs %s desde %s", file_type, file_path)

    def _load_catalog(self) -> None:
        """Carga el catálogo de NPCs desde todos los archivos."""
        # Cargar NPCs hostiles
        self._load_file(self._hostile_path, "hostiles")

        # Cargar NPCs amigables
        self._load_file(self._friendly_path, "amigables")

        logger.info("Catálogo de NPCs cargado: %d NPCs totales", len(self._npcs))

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
