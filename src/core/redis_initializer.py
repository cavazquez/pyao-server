"""Inicializador de Redis y datos iniciales."""

import logging
import time

from src.core.data_initializer import DataInitializer
from src.repositories.server_repository import ServerRepository
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

logger = logging.getLogger(__name__)


class RedisInitializer:
    """Inicializa Redis y carga datos iniciales."""

    @staticmethod
    async def initialize() -> RedisClient:
        """Conecta a Redis y carga datos iniciales.

        Returns:
            Cliente de Redis conectado y configurado.
        """
        redis_client = RedisClient()
        await redis_client.connect()
        logger.info("✓ Conectado a Redis")

        data_initializer = DataInitializer(redis_client)
        await data_initializer.initialize_all()
        logger.info("✓ Datos iniciales cargados")

        server_repo = ServerRepository(redis_client)
        await server_repo.reset_connections_count()
        logger.info("✓ Contador de conexiones reseteado")

        await server_repo.set_uptime_start(int(time.time()))
        logger.info("✓ Timestamp de inicio establecido")

        await RedisInitializer._initialize_dice_config(server_repo)
        await RedisInitializer._initialize_motd(server_repo)
        await RedisInitializer._initialize_effects_config(server_repo)

        return redis_client

    @staticmethod
    async def _initialize_dice_config(server_repo: ServerRepository) -> None:
        """Inicializa la configuración de dados en Redis si no existe."""
        dice_min_key = "server:dice:min_value"
        dice_max_key = "server:dice:max_value"

        if await server_repo.get_config(dice_min_key) is None:
            await server_repo.set_dice_min_value(6)
            logger.info("Valor mínimo de dados inicializado: 6")

        if await server_repo.get_config(dice_max_key) is None:
            await server_repo.set_dice_max_value(18)
            logger.info("Valor máximo de dados inicializado: 18")

        dice_min = await server_repo.get_dice_min_value()
        dice_max = await server_repo.get_dice_max_value()
        logger.info("Configuración de dados: min=%d, max=%d", dice_min, dice_max)

    @staticmethod
    async def _initialize_motd(server_repo: ServerRepository) -> None:
        """Inicializa el MOTD (Message of the Day) si es necesario."""
        motd = await server_repo.get_motd()
        if motd == "Bienvenido a Argentum Online!\nServidor en desarrollo.":
            initial_motd = (
                "» Bienvenido a Argentum Online! «\n"
                "• Servidor en desarrollo.\n"
                "• Usa /AYUDA para ver los comandos disponibles.\n"
                "¡Buena suerte en tu aventura!"
            )
            await server_repo.set_motd(initial_motd)
            logger.info("MOTD inicializado")

    @staticmethod
    async def _initialize_effects_config(server_repo: ServerRepository) -> None:
        """Inicializa la configuración de efectos en Redis si no existe."""
        await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED, "180")
        logger.info("Intervalo de sed configurado: 180 segundos (3 minutos)")

        await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE, "180")
        logger.info("Intervalo de hambre configurado: 180 segundos (3 minutos)")

        if await server_repo.get_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA) is None:
            await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA, "10")
            logger.info("Reducción de agua inicializada: 10 puntos")

        if await server_repo.get_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE) is None:
            await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE, "10")
            logger.info("Reducción de hambre inicializada: 10 puntos")

        if await server_repo.get_config(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED) is None:
            await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED, "1")
            logger.info("Sistema de hambre/sed habilitado por defecto")
