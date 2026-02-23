"""Configuración de fixtures para tests."""

# Parchear FakeRedisMixin para no usar argumentos deprecados de redis-py
# (retry_on_timeout; lib_name/lib_version → driver_info). Así se resuelven
# los warnings sin tocar Redis/ConnectionPool y sin romper decode_responses.
import warnings
from typing import Any

import pytest_asyncio
import redis.asyncio as redis_async
from fakeredis import aioredis
from fakeredis._helpers import convert_args_to_redis_init_kwargs  # noqa: PLC2701
from fakeredis._typing import ServerType, VersionType  # noqa: TC002
from fakeredis.aioredis import FakeConnection, FakeRedisMixin, FakeServer
from redis.driver_info import DriverInfo

from src.utils.redis_client import RedisClient


def _patched_fake_redis_mixin_init(
    self: FakeRedisMixin,
    *args: Any,  # noqa: ANN401
    server: FakeServer | None = None,
    version: VersionType = (7,),
    server_type: ServerType = "redis",
    lua_modules: set[str] | None = None,
    client_class: type = redis_async.Redis,
    **kwargs: Any,  # noqa: ANN401
) -> None:
    """Misma lógica que FakeRedisMixin.__init__ pero sin args deprecados."""
    from fakeredis._typing import lib_version as _lib_version  # noqa: PLC0415, PLC2701

    kwds = convert_args_to_redis_init_kwargs(client_class, *args, **kwargs)
    kwds.pop("retry_on_timeout", None)
    kwds["server"] = server
    kwds["connected"] = kwargs.get("connected", True)
    if not kwds.get("connection_pool", None):
        charset = kwds.get("charset", None)
        errors = kwds.get("errors", None)
        if charset is not None:
            warnings.warn(
                DeprecationWarning('"charset" is deprecated. Use "encoding" instead'),
                stacklevel=2,
            )
            kwds["encoding"] = charset
        if errors is not None:
            warnings.warn(
                DeprecationWarning('"errors" is deprecated. Use "encoding_errors" instead'),
                stacklevel=2,
            )
        # Sin retry_on_timeout (deprecated en redis 6+)
        conn_pool_args = {
            "host",
            "port",
            "db",
            "username",
            "password",
            "socket_timeout",
            "encoding",
            "encoding_errors",
            "decode_responses",
            "max_connections",
            "health_check_interval",
            "client_name",
            "connected",
            "server",
            "protocol",
        }
        connection_kwargs = {
            "connection_class": FakeConnection,
            "version": version,
            "server_type": server_type,
            "lua_modules": lua_modules,
            "client_class": client_class,
        }
        connection_kwargs.update({arg: kwds[arg] for arg in conn_pool_args if arg in kwds})
        kwds["connection_pool"] = redis_async.connection.ConnectionPool(**connection_kwargs)
    kwds.pop("server", None)
    kwds.pop("connected", None)
    kwds.pop("version", None)
    kwds.pop("server_type", None)
    kwds.pop("lua_modules", None)
    # driver_info en lugar de lib_name/lib_version (deprecated)
    kwds["driver_info"] = DriverInfo(name="fakeredis", lib_version=_lib_version)
    kwds.pop("lib_name", None)
    kwds.pop("lib_version", None)
    super(FakeRedisMixin, self).__init__(**kwds)


aioredis.FakeRedisMixin.__init__ = _patched_fake_redis_mixin_init


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
