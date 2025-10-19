"""Script para inicializar inventarios de mercaderes en Redis."""

import asyncio
import logging
import tomllib
from pathlib import Path
from typing import Any

from src.merchant_repository import MerchantRepository
from src.redis_client import RedisClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_merchant_inventories() -> dict[str, Any]:
    """Carga los inventarios de mercaderes desde el archivo TOML.

    Returns:
        Diccionario con la configuración de inventarios.
    """
    toml_path = Path(__file__).parent.parent / "data" / "merchant_inventories.toml"

    with toml_path.open("rb") as f:
        return tomllib.load(f)


async def initialize_all_merchants() -> None:
    """Inicializa los inventarios de todos los mercaderes desde el TOML."""
    # Conectar a Redis
    redis_client = RedisClient()
    await redis_client.connect()

    # Crear repositorio de mercaderes
    merchant_repo = MerchantRepository(redis_client)

    # Cargar configuración
    config = load_merchant_inventories()

    # Obtener lista de mercaderes
    merchants = config.get("merchant", [])

    if not merchants:
        logger.warning("No se encontraron mercaderes en el archivo TOML")
        await redis_client.disconnect()
        return

    # Inicializar cada mercader
    for merchant_data in merchants:
        npc_id = merchant_data.get("npc_id")
        nombre = merchant_data.get("nombre", "Mercader")
        items_data = merchant_data.get("item", [])

        if not npc_id:
            logger.warning("Mercader sin npc_id: %s", nombre)
            continue

        # Convertir inventario a formato esperado (lista de tuplas)
        items = [
            (
                item_data["item_id"],
                item_data["quantity"],
            )
            for item_data in items_data
        ]

        # Inicializar inventario
        await merchant_repo.initialize_inventory(npc_id=npc_id, items=items)
        logger.info(
            "✅ Inventario de '%s' (NPC %d) inicializado con %d items",
            nombre,
            npc_id,
            len(items),
        )

    await redis_client.disconnect()


async def main() -> None:
    """Función principal."""
    logger.info("🚀 Inicializando inventarios de mercaderes desde TOML...")

    await initialize_all_merchants()

    logger.info("✅ Todos los inventarios inicializados correctamente")


if __name__ == "__main__":
    asyncio.run(main())
