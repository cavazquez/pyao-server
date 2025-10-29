"""Loader para inicializar inventarios de mercaderes desde TOML."""

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.utils.base_data_loader import BaseDataLoader

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class MerchantDataLoader(BaseDataLoader):
    """Carga inventarios de mercaderes desde merchant_inventories.toml a Redis."""

    TOML_FILE = "data/merchant_inventories.toml"

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el loader de mercaderes.

        Args:
            redis_client: Cliente de Redis.
        """
        super().__init__(redis_client)

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del loader.

        Returns:
            Nombre del loader.
        """
        return "Merchant Inventories"

    def load(self) -> dict[int, dict[str, Any]]:
        """Carga los inventarios de mercaderes desde TOML a Redis.

        Returns:
            Diccionario de inventarios cargados. Vacío si no hay datos o ocurre un error.
        """
        try:
            inventory_data = self._load_toml_data()
        except Exception:
            logger.exception("Error cargando inventarios de mercaderes")
            return {}
        else:
            if not inventory_data:
                return {}

            total_items = 0
            for npc_id, inventory in inventory_data.items():
                npc_key = f"merchant:{npc_id}:inventory"
                for item_id, item_data in inventory.items():
                    item_key = f"{npc_key}:{item_id}"
                    self.redis_client.hset(item_key, mapping=item_data)
                    total_items += 1

                items_key = f"merchant:{npc_id}:items"
                self.redis_client.sadd(items_key, *inventory.keys())

            logger.info(
                "Cargados inventarios de %d mercaderes con %d items",
                len(inventory_data),
                total_items,
            )
            return inventory_data

    def _load_toml_data(self) -> dict[int, dict[str, Any]] | None:
        """Carga datos desde archivo TOML.

        Returns:
            Datos de inventarios o None si hay error.
        """
        toml_path = Path(self.TOML_FILE)
        if not toml_path.exists():
            logger.error("Archivo %s no encontrado", toml_path)
            return None

        try:
            with toml_path.open("rb") as f:
                return tomllib.load(f)
        except Exception:
            logger.exception("Error leyendo archivo %s", toml_path)
            return None

    def clear(self) -> None:
        """Limpia todos los inventarios de mercaderes de Redis."""
        try:
            inventory_data = self._load_toml_data()
        except Exception:
            logger.exception("Error limpiando inventarios de mercaderes")
            return

        if not inventory_data:
            return

        for npc_id in inventory_data:
            npc_key = f"merchant:{npc_id}:inventory"
            items_key = f"merchant:{npc_id}:items"
            self.redis_client.delete(npc_key)
            self.redis_client.delete(items_key)

        logger.info("Eliminados inventarios de %d mercaderes", len(inventory_data))
