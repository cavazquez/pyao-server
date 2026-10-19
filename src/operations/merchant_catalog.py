"""Migración administrativa de políticas comerciales sin reponer inventarios."""

import asyncio

from src.config.config_manager import config_manager
from src.config.game_config import RedisConfig
from src.models.merchant_data_loader import MerchantDataLoader
from src.utils.durability import require_durable
from src.utils.redis_client import RedisClient


async def migrate() -> None:
    """Adopta el catálogo TOML conservando slots y fecha de última reposición."""
    redis = RedisClient()
    settings = RedisConfig.model_validate(config_manager.get_section("redis"))
    await redis.connect(settings, seed_defaults=False)
    try:
        await require_durable(redis.redis)
        await MerchantDataLoader(redis).migrate_catalogs()
        await require_durable(redis.redis)
    finally:
        await redis.disconnect()


if __name__ == "__main__":
    asyncio.run(migrate())
