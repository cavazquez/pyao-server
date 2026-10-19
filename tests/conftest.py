"""Configuración de fixtures para tests."""

import socket
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fakeredis import aioredis

from src.utils.redis_client import RedisClient


def pytest_sessionstart() -> None:
    """Comprueba que el entorno permite despertar el event loop desde otro hilo.

    Raises:
        pytest.UsageError: Si el canal local de asyncio no funciona en este entorno.
    """
    diagnostic = (
        "El entorno no permite el canal local de asyncio (socketpair). "
        "Las pruebas requieren enviar y recibir por ese canal; sin él, "
        "asyncio.to_thread() puede quedar esperando indefinidamente. "
        "Ejecute las pruebas en un entorno con esa comunicación local habilitada."
    )
    try:
        reader, writer = socket.socketpair()
        with reader, writer:
            reader.settimeout(1)
            writer.settimeout(1)
            writer.sendall(b"\x00")
            response = reader.recv(1)
    except OSError as error:
        msg = f"{diagnostic} Error del sistema: {error}"
        raise pytest.UsageError(msg) from error
    if response != b"\x00":
        msg = f"{diagnostic} No se recibió la señal de prueba."
        raise pytest.UsageError(msg)


_REDIS_WRAPPER_METHODS = (
    "hget",
    "hset",
    "hset_field",
    "hgetall",
    "hdel",
    "hmget",
    "exists",
    "set",
    "get",
    "delete",
    "sadd",
    "smembers",
    "srem",
    "keys",
    "incr",
    "incrby",
    "decr",
    "decrby",
    "setex",
    "scard",
    "get_active_merchant",
    "set_active_merchant",
    "delete_active_merchant",
)


def create_mock_redis_client(**overrides: object) -> MagicMock:
    """Crea un MagicMock de RedisClient con todos los wrappers como AsyncMock.

    Args:
        **overrides: Métodos específicos con valores de retorno personalizados.

    Returns:
        MagicMock con los wrappers de RedisClient preconfigurados como AsyncMock.
    """
    mock = MagicMock()
    for method in _REDIS_WRAPPER_METHODS:
        setattr(mock, method, AsyncMock())
    mock.hget.return_value = None
    mock.redis.hget = AsyncMock(return_value=None)
    mock.redis.exists = AsyncMock(return_value=False)
    mock.pipeline = MagicMock()
    for key, value in overrides.items():
        setattr(mock, key, value)
    return mock


@pytest_asyncio.fixture
async def redis_client() -> RedisClient:
    """Fixture que proporciona un cliente Redis fake para tests.

    Returns:
        Cliente Redis configurado con fakeredis.
    """
    # Resetear singleton para cada test
    RedisClient._instance = None
    RedisClient._redis = None

    client = RedisClient()
    # Usar fakeredis en lugar de Redis real
    client._redis = await aioredis.FakeRedis(decode_responses=True)

    return client
