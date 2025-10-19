"""Clase base abstracta para loaders de datos."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class BaseDataLoader(ABC):
    """Clase base para todos los loaders de datos que inicializan Redis."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el loader.

        Args:
            redis_client: Cliente de Redis para almacenar datos.
        """
        self.redis_client = redis_client

    @abstractmethod
    async def load(self) -> None:
        """Carga los datos en Redis.

        Este método debe ser implementado por cada loader específico.
        Debe ser idempotente (se puede ejecutar múltiples veces sin problemas).
        """

    @abstractmethod
    def get_name(self) -> str:
        """Retorna el nombre del loader para logging.

        Returns:
            Nombre descriptivo del loader (ej: "Merchant Inventories").
        """

    async def clear(self) -> None:
        """Limpia los datos existentes en Redis (opcional).

        Por defecto no hace nada. Los loaders pueden sobrescribir este método
        si necesitan limpiar datos antes de cargar.
        """
        logger.debug("Loader %s no implementa clear()", self.get_name())

    async def initialize(self, force_clear: bool = False) -> None:
        """Inicializa los datos (con opción de limpiar primero).

        Args:
            force_clear: Si True, limpia los datos existentes antes de cargar.
        """
        logger.info("Inicializando: %s", self.get_name())

        if force_clear:
            logger.info("Limpiando datos existentes de: %s", self.get_name())
            await self.clear()

        await self.load()
        logger.info("✓ %s completado", self.get_name())
