"""Inicializador de Redis y datos iniciales."""

import logging
import time

from src.config.config_manager import ConfigManager, config_manager
from src.core.data_initializer import DataInitializer
from src.core.schema_manager import ensure_schema_ready
from src.economy.tax_migration import initialize_tax_policy
from src.repositories.account_repository import AccountRepository
from src.repositories.server_repository import ServerRepository
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisConfig, RedisKeys

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
        effective_config = RedisConfig.model_validate(config_manager.get_section("redis"))
        await redis_client.connect(effective_config, seed_defaults=False)
        await ensure_schema_ready(redis_client.redis)
        await redis_client.initialize_defaults()
        await initialize_tax_policy(
            redis_client.redis,
            enabled=bool(config_manager.get("game.tax.enabled", True)),
            percentage=float(str(config_manager.get("game.tax.daily_percentage", 1.0))),
        )
        await AccountRepository(redis_client).backfill_user_index()
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
        for key, setting in (
            (RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED, "interval_sed"),
            (RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE, "interval_hambre"),
        ):
            effective = ConfigManager.as_int(
                config_manager.get(f"game.hunger_thirst.{setting}", 180)
            )
            await server_repo.set_config_if_absent(key, str(effective))

        if await server_repo.get_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA) is None:
            await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA, "10")
            logger.info("Reducción de agua inicializada: 10 puntos")

        if await server_repo.get_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE) is None:
            await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE, "10")
            logger.info("Reducción de hambre inicializada: 10 puntos")

        if await server_repo.get_config(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED) is None:
            await server_repo.set_config(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED, "1")
            logger.info("Sistema de hambre/sed habilitado por defecto")
