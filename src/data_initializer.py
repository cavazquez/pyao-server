"""Orquestador principal para inicializar todos los datos en Redis."""

import logging
from typing import TYPE_CHECKING

from src.merchant_data_loader import MerchantDataLoader

if TYPE_CHECKING:
    from src.base_data_loader import BaseDataLoader
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class DataInitializer:
    """Orquesta la inicialización de todos los loaders de datos."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el orquestador de datos.

        Args:
            redis_client: Cliente de Redis compartido por todos los loaders.
        """
        self.redis_client = redis_client

        # Lista de loaders a ejecutar (en orden)
        self.loaders: list[BaseDataLoader] = [
            MerchantDataLoader(redis_client),
        ]

    async def initialize_all(self, force_clear: bool = False) -> None:
        """Inicializa todos los loaders de datos.

        Args:
            force_clear: Si True, limpia los datos existentes antes de cargar.
        """
        logger.info("=== Iniciando carga de datos en Redis ===")

        total_loaders = len(self.loaders)
        for idx, loader in enumerate(self.loaders, 1):
            logger.info("[%d/%d] %s", idx, total_loaders, loader.get_name())
            await loader.initialize(force_clear=force_clear)

        logger.info("=== ✓ Todos los datos han sido inicializados ===")

    async def initialize_specific(self, loader_name: str, force_clear: bool = False) -> bool:
        """Inicializa un loader específico por nombre.

        Args:
            loader_name: Nombre del loader a ejecutar.
            force_clear: Si True, limpia los datos existentes antes de cargar.

        Returns:
            True si el loader fue encontrado y ejecutado, False si no existe.
        """
        for loader in self.loaders:
            if loader.get_name().lower() == loader_name.lower():
                logger.info("Inicializando loader específico: %s", loader.get_name())
                await loader.initialize(force_clear=force_clear)
                return True

        logger.error("Loader '%s' no encontrado", loader_name)
        return False

    def list_loaders(self) -> list[str]:
        """Retorna la lista de nombres de loaders disponibles.

        Returns:
            Lista de nombres de loaders.
        """
        return [loader.get_name() for loader in self.loaders]
