"""Catálogo de hechizos del juego."""

import logging
import tomllib
from pathlib import Path
from typing import Any

from src.models.items_catalog import ITEMS_CATALOG
from src.models.spell_extensions import validate_extensions
from src.runtime_paths import data_dir

logger = logging.getLogger(__name__)


class SpellCatalog:
    """Catálogo de hechizos disponibles en el juego."""

    def __init__(self, spells_path: str | None = None) -> None:
        """Inicializa el catálogo de hechizos.

        Args:
            spells_path: Ruta al archivo de hechizos.
        """
        self.spells: dict[int, dict[str, Any]] = {}
        self.path = spells_path or str(data_dir() / "spells.toml")
        self._load_spells(self.path)

    def reload(self) -> int:
        """Valida antes de sustituir hechizos, sin invalidar libros persistidos.

        Returns:
            Número de hechizos cargados.

        Raises:
            ValueError: Si desaparece un hechizo existente.
        """
        candidate = SpellCatalog(self.path)
        if not self.spells.keys() <= candidate.spells.keys():
            message = "La recarga no puede eliminar hechizos existentes"
            raise ValueError(message)
        self.spells = candidate.spells
        return len(self.spells)

    def _load_spells(self, spells_path: str) -> None:
        """Carga los hechizos desde el archivo TOML.

        Args:
            spells_path: Ruta al archivo de hechizos.

        Raises:
            ValueError: Si una referencia o regla de magia es inválida.
            TypeError: Si el catálogo contiene tipos inválidos.
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

                validate_extensions(spell_data, set(ITEMS_CATALOG))

                self.spells[spell_id] = spell_data
                spell_name = spell_data.get("name", "Unknown")
                logger.info(
                    "Hechizo cargado: ID=%d, Nombre='%s', Mana=%d, Daño=%d-%d",
                    spell_id,
                    spell_name,
                    spell_data.get("mana_cost", 0),
                    spell_data.get("min_damage", 0),
                    spell_data.get("max_damage", 0),
                )

            logger.info(
                "✓ Catálogo de hechizos cargado exitosamente: %d hechizos disponibles",
                len(self.spells),
            )

        except ValueError, TypeError:
            raise
        except OSError:
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
