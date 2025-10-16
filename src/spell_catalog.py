"""Catálogo de hechizos del juego."""

import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SpellCatalog:
    """Catálogo de hechizos disponibles en el juego."""

    def __init__(self, spells_path: str = "data/spells.toml") -> None:
        """Inicializa el catálogo de hechizos.

        Args:
            spells_path: Ruta al archivo de hechizos.
        """
        self.spells: dict[int, dict[str, Any]] = {}
        self._load_spells(spells_path)

    def _load_spells(self, spells_path: str) -> None:
        """Carga los hechizos desde el archivo TOML.

        Args:
            spells_path: Ruta al archivo de hechizos.
        """
        path = Path(spells_path)
        if not path.exists():
            logger.warning("Archivo de hechizos no encontrado: %s", spells_path)
            return

        try:
            with path.open("rb") as f:
                data = tomllib.load(f)

            if "spell" not in data:
                logger.warning("No se encontró la sección [spell] en %s", spells_path)
                return

            for spell_data in data["spell"]:
                spell_id = spell_data.get("id")
                if spell_id is None:
                    logger.warning("Hechizo sin ID, ignorando")
                    continue

                self.spells[spell_id] = spell_data
                logger.debug("Cargado hechizo: %s (ID: %d)", spell_data.get("name"), spell_id)

            logger.info("Catálogo de hechizos cargado: %d hechizos", len(self.spells))

        except Exception:
            logger.exception("Error al cargar catálogo de hechizos")

    def spell_exists(self, spell_id: int) -> bool:
        """Verifica si un hechizo existe en el catálogo.

        Args:
            spell_id: ID del hechizo.

        Returns:
            True si el hechizo existe, False en caso contrario.
        """
        return spell_id in self.spells

    def get_spell_data(self, spell_id: int) -> dict[str, Any] | None:
        """Obtiene los datos de un hechizo.

        Args:
            spell_id: ID del hechizo.

        Returns:
            Diccionario con los datos del hechizo o None si no existe.
        """
        return self.spells.get(spell_id)

    def get_all_spell_ids(self) -> list[int]:
        """Obtiene todos los IDs de hechizos disponibles.

        Returns:
            Lista de IDs de hechizos.
        """
        return list(self.spells.keys())
