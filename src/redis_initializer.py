"""Inicializador de Redis y datos iniciales."""

import logging
import time

from src.data_initializer import DataInitializer
from src.redis_client import RedisClient
from src.redis_config import RedisKeys
from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class RedisInitializer:
    """Inicializa Redis y carga datos iniciales."""

    @staticmethod
    async def initialize() -> RedisClient:
        """Conecta a Redis y carga datos iniciales.

        Returns:
            Cliente de Redis conectado y configurado.
        """
        # Conectar a Redis
        redis_client = RedisClient()
        await redis_client.connect()
        logger.info("✓ Conectado a Redis")

        # Cargar datos iniciales (items, NPCs, merchants, etc.)
        data_initializer = DataInitializer(redis_client)
        await data_initializer.initialize_all()
        logger.info("✓ Datos iniciales cargados")

        # Resetear contador de conexiones
        await redis_client.redis.set("server:connections:count", "0")
        logger.info("✓ Contador de conexiones reseteado")

        # Establecer timestamp de inicio del servidor
        server_repo = ServerRepository(redis_client)
        await server_repo.set_uptime_start(int(time.time()))
        logger.info("✓ Timestamp de inicio establecido")

        # Inicializar configuración de dados
        await RedisInitializer._initialize_dice_config(redis_client, server_repo)

        # Inicializar MOTD
        await RedisInitializer._initialize_motd(server_repo)

        # Inicializar configuración de efectos
        await RedisInitializer._initialize_effects_config(redis_client)

        return redis_client

    @staticmethod
    async def _initialize_dice_config(
        redis_client: RedisClient, server_repo: ServerRepository
    ) -> None:
        """Inicializa la configuración de dados en Redis si no existe."""
        dice_min_key = "server:dice:min_value"
        dice_max_key = "server:dice:max_value"

        # Verificar si existen, si no, crear con valores por defecto
        if await redis_client.redis.get(dice_min_key) is None:
            await server_repo.set_dice_min_value(6)
            logger.info("Valor mínimo de dados inicializado: 6")

        if await redis_client.redis.get(dice_max_key) is None:
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
            # Es el mensaje por defecto, establecer uno inicial
            initial_motd = (
                "» Bienvenido a Argentum Online! «\n"
                "• Servidor en desarrollo.\n"
                "• Usa /AYUDA para ver los comandos disponibles.\n"
                "¡Buena suerte en tu aventura!"
            )
            await server_repo.set_motd(initial_motd)
            logger.info("MOTD inicializado")

    @staticmethod
    async def _initialize_effects_config(redis_client: RedisClient) -> None:
        """Inicializa la configuración de efectos en Redis si no existe."""
        # Hambre y Sed - 180 segundos (3 minutos)
        # SIEMPRE establecer valores correctos (sobrescribe valores de testing)
        await redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED, "180")
        logger.info("Intervalo de sed configurado: 180 segundos (3 minutos)")

        await redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE, "180")
        logger.info("Intervalo de hambre configurado: 180 segundos (3 minutos)")

        if await redis_client.redis.get(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA) is None:
            await redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA, "10")
            logger.info("Reducción de agua inicializada: 10 puntos")

        if await redis_client.redis.get(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE) is None:
            await redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE, "10")
            logger.info("Reducción de hambre inicializada: 10 puntos")

        if await redis_client.redis.get(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED) is None:
            await redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED, "1")
            logger.info("Sistema de hambre/sed habilitado por defecto")
