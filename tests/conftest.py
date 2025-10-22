"""Configuración de fixtures para tests."""

import pytest_asyncio
from fakeredis import aioredis

from src.utils.redis_client import RedisClient


@pytest_asyncio.fixture
async def redis_client() -> RedisClient:
    """Fixture que proporciona un cliente Redis fake para tests.

    Returns:
        Cliente Redis configurado con fakeredis.
    """
    # Resetear singleton para cada test
    RedisClient._instance = None  # noqa: SLF001
    RedisClient._redis = None  # noqa: SLF001

    client = RedisClient()
    # Usar fakeredis en lugar de Redis real
    client._redis = await aioredis.FakeRedis(decode_responses=True)  # noqa: SLF001

    return client
