"""Loader para inicializar inventarios de mercaderes desde TOML."""

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from src.base_data_loader import BaseDataLoader
from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient

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

    async def load(self) -> None:
        """Carga los inventarios de mercaderes desde TOML a Redis."""
        toml_path = Path(self.TOML_FILE)
        if not toml_path.exists():  # noqa: ASYNC240
            logger.error("Archivo %s no encontrado", toml_path)
            return

        # Cargar archivo TOML
        with toml_path.open("rb") as f:  # noqa: ASYNC230
            data = tomllib.load(f)

        merchants = data.get("merchant", [])
        if not merchants:
            logger.warning("No se encontraron mercaderes en %s", toml_path)
            return

        # Procesar cada mercader
        total_merchants = 0
        total_items = 0

        for merchant in merchants:
            npc_id = merchant.get("npc_id")
            nombre = merchant.get("nombre", f"Mercader {npc_id}")
            items = merchant.get("item", [])

            if not npc_id:
                logger.warning("Mercader sin npc_id, saltando...")
                continue

            logger.debug("Cargando inventario de %s (npc_id=%d)", nombre, npc_id)

            # Agregar items al inventario
            key = RedisKeys.merchant_inventory(npc_id)
            slot = 1

            for item in items:
                item_id = item.get("item_id")
                quantity = item.get("quantity", 1)

                if not item_id:
                    logger.warning("Item sin item_id en mercader %s, saltando...", nombre)
                    continue

                slot_key = f"slot_{slot}"
                value = f"{item_id}:{quantity}"
                await self.redis_client.redis.hset(key, slot_key, value)  # type: ignore[misc]

                slot += 1
                total_items += 1

            total_merchants += 1
            logger.debug("  → %d items cargados", len(items))

        logger.info("Cargados %d mercaderes con %d items totales", total_merchants, total_items)

    async def clear(self) -> None:
        """Limpia todos los inventarios de mercaderes existentes."""
        # Cargar archivo para obtener los npc_ids
        toml_path = Path(self.TOML_FILE)
        if not toml_path.exists():  # noqa: ASYNC240
            return

        with toml_path.open("rb") as f:  # noqa: ASYNC230
            data = tomllib.load(f)

        merchants = data.get("merchant", [])

        for merchant in merchants:
            npc_id = merchant.get("npc_id")
            if npc_id:
                key = RedisKeys.merchant_inventory(npc_id)
                await self.redis_client.redis.delete(key)
                logger.debug("Limpiado inventario de mercader npc_id=%d", npc_id)
