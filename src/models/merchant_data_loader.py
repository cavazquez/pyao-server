"""Loader para inicializar inventarios de mercaderes desde TOML."""

import asyncio
import inspect
import logging
import tomllib
from collections.abc import Awaitable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from src.utils.base_data_loader import BaseDataLoader
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

_RedisResultT = TypeVar("_RedisResultT")

logger = logging.getLogger(__name__)


class MerchantDataLoader(BaseDataLoader):
    """Carga inventarios de mercaderes desde merchant_inventories.toml a Redis."""

    TOML_FILE = "data/npcs/merchants.toml"

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el loader de mercaderes.

        Args:
            redis_client: Cliente de Redis.
        """
        super().__init__(redis_client)

    def get_name(self) -> str:
        """Retorna el nombre del loader.

        Returns:
            Nombre del loader.
        """
        return "Merchant Inventories"

    async def load(self) -> None:
        """Carga los inventarios de mercaderes desde TOML a Redis."""
        merchants = await self._load_inventory_data()
        if not merchants:
            logger.warning("No se encontraron inventarios de mercaderes para cargar")
            return

        redis = self.redis_client.redis
        total_items = 0
        merchants_loaded = 0

        for merchant in merchants:
            npc_id = self._extract_npc_id(merchant)
            if npc_id is None:
                continue

            items = self._extract_items(merchant)
            if items is None:
                continue

            inventory_key = RedisKeys.merchant_inventory(npc_id)
            await self._execute_redis(redis.delete(inventory_key))

            slot = 1
            item_ids: list[str] = []
            for item in items:
                formatted_item = self._format_item(item, npc_id)
                if formatted_item is None:
                    continue

                item_id, quantity = formatted_item
                slot_key = f"slot_{slot}"
                value = f"{item_id}:{quantity}"
                await self._execute_redis(redis.hset(inventory_key, slot_key, value))
                item_ids.append(str(item_id))
                total_items += 1
                slot += 1

            if item_ids:
                items_key = self._merchant_items_key(npc_id)
                await self._execute_redis(redis.delete(items_key))
                await self._execute_redis(redis.sadd(items_key, *item_ids))

            merchants_loaded += 1

        logger.info(
            "Cargados inventarios de %d mercaderes con %d items",
            merchants_loaded,
            total_items,
        )

    async def clear(self) -> None:
        """Limpia todos los inventarios de mercaderes de Redis."""
        merchants = await self._load_inventory_data()
        if not merchants:
            logger.warning("No hay inventarios de mercaderes para limpiar")
            return

        redis = self.redis_client.redis
        deleted = 0

        for merchant in merchants:
            npc_id = self._extract_npc_id(merchant)
            if npc_id is None:
                continue

            await self._execute_redis(redis.delete(RedisKeys.merchant_inventory(npc_id)))
            await self._execute_redis(redis.delete(self._merchant_items_key(npc_id)))
            deleted += 1

        logger.info("Eliminados inventarios de %d mercaderes", deleted)

    async def _load_inventory_data(self) -> list[dict[str, Any]] | None:
        """Lee y valida el archivo TOML con inventarios de mercaderes.

        Returns:
            Lista de definiciones de mercaderes o ``None`` si el archivo no se pudo leer.
        """
        data = await asyncio.to_thread(self._read_toml_file)
        if not data:
            return None

        merchants = data.get("merchant")
        if not isinstance(merchants, list):
            logger.error("Archivo %s inválido: se esperaba una lista 'merchant'", self.TOML_FILE)
            return None

        return merchants

    def _read_toml_file(self) -> dict[str, Any] | None:
        """Carga datos desde archivo TOML.

        Returns:
            Diccionario con los datos cargados o ``None`` si ocurre un error.
        """
        toml_path = Path(self.TOML_FILE)
        if not toml_path.exists():
            logger.error("Archivo %s no encontrado", toml_path)
            return None

        try:
            with toml_path.open("rb") as file:
                return tomllib.load(file)
        except Exception:
            logger.exception("Error leyendo archivo %s", toml_path)
            return None

    @staticmethod
    def _extract_npc_id(merchant: dict[str, Any]) -> int | None:
        """Obtiene y valida el npc_id de la entrada del mercader.

        Returns:
            ID del mercader o ``None`` si la entrada es inválida.
        """
        npc_id_raw = merchant.get("npc_id")
        if npc_id_raw is None:
            logger.warning("Mercader sin npc_id: %s", merchant)
            return None

        try:
            return int(npc_id_raw)
        except (TypeError, ValueError):
            logger.warning("npc_id inválido para mercader: %s", npc_id_raw)
            return None

    @staticmethod
    def _extract_items(merchant: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Obtiene la lista de items de la entrada del mercader.

        Returns:
            Lista de items o ``None`` si el formato es inválido.
        """
        items = merchant.get("item")
        if items is None:
            logger.debug("Mercader %s sin items configurados", merchant)
            return []

        if isinstance(items, list):
            return items

        logger.warning("Formato de items inválido para mercader: %s", merchant)
        return None

    @staticmethod
    def _format_item(item: dict[str, Any], npc_id: int) -> tuple[int, int] | None:
        """Valida y formatea un item para guardarlo en Redis.

        Returns:
            Tupla ``(item_id, quantity)`` o ``None`` si el item es inválido.
        """
        try:
            item_id = int(item["item_id"])
            quantity = int(item.get("quantity", 0))
        except (KeyError, TypeError, ValueError):
            logger.warning("Item inválido en mercader %d: %s", npc_id, item)
            return None

        if quantity < 0:
            logger.warning(
                "Cantidad negativa para item %d de mercader %d: %d",
                item_id,
                npc_id,
                quantity,
            )
            return None

        return item_id, quantity

    @staticmethod
    def _merchant_items_key(npc_id: int) -> str:
        """Clave del conjunto de items de un mercader.

        Returns:
            Nombre de la clave en Redis para el conjunto de items.
        """
        return f"merchant:{npc_id}:items"

    @staticmethod
    async def _execute_redis(
        result: Awaitable[_RedisResultT] | _RedisResultT,
    ) -> _RedisResultT:
        """Compatibilidad con comandos Redis que pueden ser sync o async.

        Returns:
            Resultado del comando ejecutado.
        """
        if inspect.isawaitable(result):
            return await result
        return result
