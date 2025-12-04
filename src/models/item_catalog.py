"""Catálogo de items cargado desde items.toml."""

import logging
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

# ObjType constants from Argentum Online
OBJTYPE_WEAPON = 2
OBJTYPE_ARMOR = 4


class ItemCatalog:
    """Gestiona el catálogo de items desde el archivo data/items.toml."""

    def __init__(self, data_path: str = "data/items.toml") -> None:
        """Inicializa el catálogo de items.

        Args:
            data_path: Ruta al archivo items.toml.
        """
        self._items: dict[int, dict[str, object]] = {}
        self._data_path = data_path
        self._load_catalog()

    def _load_catalog(self) -> None:
        """Carga el catálogo de items desde el archivo TOML."""
        try:
            path = Path(self._data_path)
            items_loaded = 0

            # Nuevo formato: directorio data/items/ con múltiples archivos
            items_dir = path.parent / "items"
            if items_dir.exists() and items_dir.is_dir():
                toml_files = sorted(items_dir.glob("**/*.toml"))
                toml_files = [f for f in toml_files if f.stem.lower() != "readme"]

                for toml_file in toml_files:
                    with toml_file.open("rb") as f:
                        data = tomllib.load(f)

                    for item_data in data.get("item", []):
                        item_id = item_data.get("id")
                        if item_id is None:
                            logger.warning(
                                "Item sin ID encontrado en %s, ignorando: %s",
                                toml_file,
                                item_data,
                            )
                            continue

                        self._items[item_id] = item_data
                        items_loaded += 1

                if items_loaded:
                    logger.info(
                        "Catálogo de items cargado desde %s: %d items",
                        items_dir,
                        items_loaded,
                    )
                    return

            # Formato legacy: archivo único items.toml
            if not path.exists():
                logger.warning("Archivo de items no encontrado: %s", self._data_path)
                return

            with path.open("rb") as f:
                data = tomllib.load(f)

            if "item" not in data:
                logger.warning("No se encontró la sección [item] en %s", self._data_path)
                return

            for item_data in data["item"]:
                item_id = item_data.get("id")
                if item_id is None:
                    logger.warning("Item sin ID encontrado, ignorando: %s", item_data)
                    continue

                self._items[item_id] = item_data
                items_loaded += 1

            logger.info(
                "Catálogo de items cargado desde %s: %d items",
                self._data_path,
                items_loaded,
            )

        except Exception:
            logger.exception("Error al cargar catálogo de items desde %s", self._data_path)

    def get_item_data(self, item_id: int) -> dict[str, object] | None:
        """Obtiene los datos de un item por su ID.

        Args:
            item_id: ID del item en el catálogo.

        Returns:
            Diccionario con los datos del item o None si no existe.
        """
        return self._items.get(item_id)

    def get_grh_index(self, item_id: int) -> int | None:
        """Obtiene el GrhIndex de un item.

        Args:
            item_id: ID del item.

        Returns:
            GrhIndex del item o None si no existe.
        """
        item = self._items.get(item_id)
        if item:
            return item.get("GrhIndex")  # type: ignore[return-value]
        return None

    def get_item_name(self, item_id: int) -> str | None:
        """Obtiene el nombre de un item.

        Args:
            item_id: ID del item.

        Returns:
            Nombre del item o None si no existe.
        """
        item = self._items.get(item_id)
        if item:
            return item.get("Name")  # type: ignore[return-value]
        return None

    def item_exists(self, item_id: int) -> bool:
        """Verifica si un item existe en el catálogo.

        Args:
            item_id: ID del item.

        Returns:
            True si existe, False si no.
        """
        return item_id in self._items

    def get_weapon_damage(self, item_id: int) -> tuple[int, int] | None:
        """Obtiene el daño mínimo y máximo de un arma.

        Args:
            item_id: ID del item (debe ser un arma, ObjType=OBJTYPE_WEAPON).

        Returns:
            Tupla (min_hit, max_hit) o None si no es un arma o no existe.
        """
        item = self._items.get(item_id)
        if not item:
            return None

        if item.get("ObjType") != OBJTYPE_WEAPON:
            return None

        min_hit = item.get("MinHit", 1)
        max_hit = item.get("MaxHit", 1)

        # Asegurar que son enteros
        if isinstance(min_hit, int) and isinstance(max_hit, int):
            return (min_hit, max_hit)

        # Cast a int para valores no-int (float, str, etc.)
        return (int(str(min_hit)), int(str(max_hit)))

    def get_armor_defense(self, item_id: int) -> tuple[int, int] | None:
        """Obtiene la defensa mínima y máxima de una armadura.

        Args:
            item_id: ID del item (debe ser una armadura, ObjType=OBJTYPE_ARMOR).

        Returns:
            Tupla (min_def, max_def) o None si no es armadura o no existe.
        """
        item = self._items.get(item_id)
        if not item:
            return None

        if item.get("ObjType") != OBJTYPE_ARMOR:
            return None

        min_def = item.get("MinDef", 0)
        max_def = item.get("MaxDef", 0)

        # Asegurar que son enteros
        if isinstance(min_def, int) and isinstance(max_def, int):
            return (min_def, max_def)

        # Cast a int para valores no-int (float, str, etc.)
        return (int(str(min_def)), int(str(max_def)))
