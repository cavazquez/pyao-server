"""El arranque preserva la configuración persistida de hambre y sed."""

import asyncio
from unittest.mock import patch

import pytest

from src.config.config_manager import config_manager
from src.core.redis_initializer import RedisInitializer
from src.repositories.server_repository import ServerRepository
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "existing",
    [RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED, RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE],
)
async def test_existing_interval_survives_concurrent_default_and_effect_initializers(
    redis_client, existing
):
    """Un valor previo se conserva y la clave ausente recibe su default efectivo propio."""
    repo = ServerRepository(redis_client)
    await redis_client.set(existing, "321")
    defaults = {"game.hunger_thirst.interval_sed": 717, "game.hunger_thirst.interval_hambre": 919}
    with patch.object(
        config_manager, "get", side_effect=lambda key, default=None: defaults.get(key, default)
    ):
        for _ in range(2):
            await asyncio.gather(
                redis_client.initialize_defaults(),
                RedisInitializer._initialize_effects_config(repo),
                RedisInitializer._initialize_effects_config(repo),
            )
    assert await redis_client.get(existing) == "321"
    if existing == RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED:
        assert await redis_client.get(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE) == "919"
    else:
        assert await redis_client.get(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED) == "717"
