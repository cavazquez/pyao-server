"""Catálogo de NPCs cargado desde npcs.toml."""

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)


class NPCCatalog:
    """Gestiona el catálogo de NPCs desde archivos TOML.

    El catálogo contiene las plantillas de NPCs que se pueden instanciar
    en el mundo. Cada NPC tiene un ID único y propiedades base.

    Carga NPCs desde múltiples archivos:
    - npcs_hostiles.toml: Criaturas agresivas
    - npcs_amigables.toml: NPCs de servicios
    - npcs.toml: Archivo legacy (retrocompatibilidad)
    """

    def __init__(
        self,
        data_path: str | None = None,  # Retrocompatibilidad
        hostile_path: str = "data/npcs_hostiles.toml",
        friendly_path: str = "data/npcs_amigables.toml",
        legacy_path: str = "data/npcs.toml",
    ) -> None:
        """Inicializa el catálogo de NPCs.

        Args:
            data_path: Ruta al archivo legacy (retrocompatibilidad con tests).
            hostile_path: Ruta al archivo de NPCs hostiles.
            friendly_path: Ruta al archivo de NPCs amigables.
            legacy_path: Ruta al archivo legacy (retrocompatibilidad).
        """
        self._npcs: dict[int, dict[str, object]] = {}

        # Retrocompatibilidad: si se pasa data_path, usarlo como legacy_path
        if data_path is not None:
            self._hostile_path = ""
            self._friendly_path = ""
            self._legacy_path = data_path
        else:
            self._hostile_path = hostile_path
            self._friendly_path = friendly_path
            self._legacy_path = legacy_path

        self._load_catalog()

    def _load_file(self, file_path: str, file_type: str) -> None:
        """Carga NPCs desde un archivo TOML.

        Args:
            file_path: Ruta al archivo.
            file_type: Tipo de archivo para logging (hostile/friendly/legacy).
        """
        # Skip si el path está vacío (retrocompatibilidad)
        if not file_path:
            return

        try:
            path = Path(file_path)
            if not path.exists():
                logger.debug("Archivo de NPCs %s no encontrado: %s", file_type, file_path)
                return

            with path.open("rb") as f:
                data = tomllib.load(f)

            if "npc" not in data:
                logger.warning("No se encontró la sección [npc] en %s", file_path)
                return

            count = 0
            for npc_data in data["npc"]:
                npc_id = npc_data.get("id")
                if npc_id is None:
                    logger.warning("NPC sin ID encontrado, ignorando: %s", npc_data)
                    continue

                self._npcs[npc_id] = npc_data
                logger.debug("NPC cargado: %d - %s", npc_id, npc_data.get("nombre", "Sin nombre"))
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

        # Cargar archivo legacy si existe (retrocompatibilidad)
        self._load_file(self._legacy_path, "legacy")

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
