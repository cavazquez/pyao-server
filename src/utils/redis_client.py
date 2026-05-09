"""Cliente Redis singleton para el servidor."""

import logging
import time
from typing import Any, Self, cast

import redis.asyncio as redis

from src.utils.redis_config import (
    DEFAULT_EFFECTS_CONFIG,
    DEFAULT_SERVER_CONFIG,
    RedisConfig,
    RedisKeys,
)

logger = logging.getLogger(__name__)


def _ensure_ping_success(result: bool) -> None:
    if not result:
        error_msg = "Redis ping failed"
        raise redis.ConnectionError(error_msg)


class RedisClient:
    """Cliente Redis singleton con soporte async."""

    _instance: RedisClient | None = None
    _redis: redis.Redis | None = None

    def __new__(cls) -> Self:
        """Implementa el patrón singleton."""
        if cls._instance is None:
            cls._instance = cast("RedisClient", super().__new__(cls))
        return cast("Self", cls._instance)

    async def connect(self, config: RedisConfig | None = None) -> None:
        """Conecta al servidor Redis.

        Args:
            config: Configuración de Redis. Si es None, usa valores por defecto.

        Raises:
            ConnectionError: Si no se puede conectar a Redis (puerto cerrado, host inaccesible).
            RedisError: Si hay otro error al conectar a Redis.
        """
        if self._redis is not None:
            logger.warning("Redis ya está conectado")
            return

        if config is None:
            config = RedisConfig()

        try:
            self._redis = redis.Redis(
                host=config.host,
                port=config.port,
                db=config.db,
                decode_responses=config.decode_responses,
                socket_timeout=config.socket_timeout,
                socket_connect_timeout=config.socket_connect_timeout,
            )
            ping_response = self._redis.ping()
            if isinstance(ping_response, bool):
                _ensure_ping_success(ping_response)
            else:
                awaited_result = await ping_response
                _ensure_ping_success(awaited_result)
            logger.info("Conectado a Redis en %s:%d", config.host, config.port)

            await self._initialize_default_config()

        except redis.ConnectionError as e:
            logger.warning("No se pudo conectar a Redis en %s:%d - %s", config.host, config.port, e)
            self._redis = None
            raise
        except redis.RedisError:
            logger.exception("Error al conectar a Redis")
            self._redis = None
            raise

    async def _initialize_default_config(self) -> None:
        """Inicializa la configuración por defecto en Redis si no existe."""
        if self._redis is None:
            return

        for key, value in DEFAULT_SERVER_CONFIG.items():
            exists = await self._redis.exists(key)
            if not exists:
                await self._redis.set(key, value)
                logger.info("Configuración inicializada: %s = %s", key, value)

        for key, value in DEFAULT_EFFECTS_CONFIG.items():
            exists = await self._redis.exists(key)
            if not exists:
                await self._redis.set(key, value)
                logger.info("Configuración de efecto inicializada: %s = %s", key, value)

    async def disconnect(self) -> None:
        """Desconecta del servidor Redis."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("Desconectado de Redis")

    @property
    def is_connected(self) -> bool:
        """True si Redis está conectado."""
        return self._redis is not None

    @property
    def redis(self) -> redis.Redis:
        """Propiedad legacy. Preferir usar los wrappers (hget, hset, etc.)."""
        if self._redis is None:
            msg = "Redis no está conectado. Llama a connect() primero."
            raise RuntimeError(msg)
        return self._redis

    # ── Core Redis wrappers ────────────────────────────────────────────

    async def hget(self, key: str, field: str) -> str | None:
        """Lee un campo de un hash."""
        return await self._redis.hget(key, field)  # type: ignore[union-attr,no-any-return]

    async def hset(
        self,
        key: str,
        field: str | dict[str, str] | None = None,
        value: str | None = None,
        *,
        mapping: dict[str, str] | None = None,
    ) -> int:
        """Escribe campos en un hash.

        Usa hset_field(key, field, value) para campo único.
        Usa hset(key, mapping={...}) para múltiples campos.
        También acepta hset(key, dict) como shortcut para mapping.
        """
        if mapping is not None:
            return await self._redis.hset(key, mapping=mapping)  # type: ignore[union-attr,no-any-return]
        if isinstance(field, dict):
            return await self._redis.hset(key, mapping=field)  # type: ignore[union-attr,no-any-return]
        if field is not None and value is not None:
            return await self._redis.hset(key, field, value)  # type: ignore[union-attr,no-any-return]
        return 0

    async def hset_field(self, key: str, field: str, value: str) -> int:
        """Escribe un solo campo en un hash."""
        return await self._redis.hset(key, field, value)  # type: ignore[union-attr,no-any-return]

    async def hgetall(self, key: str) -> dict[str, str]:
        """Lee todos los campos de un hash."""
        return await self._redis.hgetall(key)  # type: ignore[union-attr,no-any-return]

    async def hdel(self, key: str, *fields: str) -> int:
        """Elimina campos de un hash."""
        return await self._redis.hdel(key, *fields)  # type: ignore[union-attr,no-any-return]

    async def hmget(self, key: str, fields: list[str]) -> list[str | None]:
        """Lee múltiples campos de un hash."""
        return await self._redis.hmget(key, fields)  # type: ignore[union-attr,no-any-return]

    async def exists(self, key: str) -> int:
        """Verifica si una key existe."""
        return await self._redis.exists(key)  # type: ignore[union-attr,no-any-return]

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """Establece el valor de una key.

        Args:
            key: Clave.
            value: Valor.
            ex: TTL en segundos (opcional).
        """
        return await self._redis.set(key, value, ex=ex)  # type: ignore[union-attr,no-any-return]

    async def get(self, key: str) -> str | None:
        """Obtiene el valor de una key."""
        return await self._redis.get(key)  # type: ignore[union-attr,no-any-return]

    async def delete(self, *keys: str) -> int:
        """Elimina una o más keys."""
        return await self._redis.delete(*keys)  # type: ignore[union-attr,no-any-return]

    async def sadd(self, key: str, *members: str) -> int:
        """Agrega miembros a un set."""
        return await self._redis.sadd(key, *members)  # type: ignore[union-attr,no-any-return]

    async def smembers(self, key: str) -> set[str]:  # type: ignore[valid-type]
        """Obtiene todos los miembros de un set."""
        return await self._redis.smembers(key)  # type: ignore[union-attr,no-any-return]

    async def srem(self, key: str, *members: str) -> int:
        """Remueve miembros de un set."""
        return await self._redis.srem(key, *members)  # type: ignore[union-attr,no-any-return]

    async def keys(self, pattern: str) -> list[str]:
        """Busca keys por patrón."""
        return await self._redis.keys(pattern)  # type: ignore[union-attr,no-any-return]

    async def incr(self, key: str) -> int:
        """Incrementa una key en 1."""
        return await self._redis.incr(key)  # type: ignore[union-attr,no-any-return]

    async def incrby(self, key: str, amount: int) -> int:
        """Incrementa una key por amount."""
        return await self._redis.incrby(key, amount)  # type: ignore[union-attr,no-any-return]

    async def decr(self, key: str) -> int:
        """Decrementa una key en 1."""
        return await self._redis.decr(key)  # type: ignore[union-attr,no-any-return]

    async def decrby(self, key: str, amount: int) -> int:
        """Decrementa una key por amount."""
        return await self._redis.decrby(key, amount)  # type: ignore[union-attr,no-any-return]

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        """Establece una key con TTL."""
        return await self._redis.setex(key, seconds, value)  # type: ignore[union-attr,no-any-return]

    async def scard(self, key: str) -> int:
        """Tamaño de un set."""
        return await self._redis.scard(key)  # type: ignore[union-attr,no-any-return]

    def pipeline(self, transaction: bool = True) -> redis.client.Pipeline:  # type: ignore[name-defined]
        """Crea un pipeline Redis para operaciones atómicas."""
        return self._redis.pipeline(transaction=transaction)  # type: ignore[union-attr]

    async def flushdb(self) -> bool:
        """Limpia toda la base de datos (solo para tests)."""
        return await self._redis.flushdb()  # type: ignore[union-attr,no-any-return]

    # ── Server config ──────────────────────────────────────────────────

    async def get_server_host(self) -> str:
        """Obtiene el host del servidor desde Redis."""
        value = await self.get(RedisKeys.CONFIG_SERVER_HOST)
        return value if value is not None else "0.0.0.0"

    async def get_server_port(self) -> int:
        """Obtiene el puerto del servidor desde Redis."""
        value = await self.get(RedisKeys.CONFIG_SERVER_PORT)
        return int(value) if value is not None else 7666

    async def set_server_host(self, host: str) -> None:
        """Establece el host del servidor en Redis."""
        await self.set(RedisKeys.CONFIG_SERVER_HOST, host)
        logger.info("Host del servidor actualizado: %s", host)

    async def set_server_port(self, port: int) -> None:
        """Establece el puerto del servidor en Redis."""
        await self.set(RedisKeys.CONFIG_SERVER_PORT, str(port))
        logger.info("Puerto del servidor actualizado: %d", port)

    # ── Connection counters ────────────────────────────────────────────

    async def increment_connections(self) -> int:
        """Incrementa el contador de conexiones activas."""
        count = await self.incr(RedisKeys.SERVER_CONNECTIONS_COUNT)
        return int(count) if isinstance(count, (int, str)) else 0

    async def decrement_connections(self) -> int:
        """Decrementa el contador de conexiones activas."""
        count = await self.decr(RedisKeys.SERVER_CONNECTIONS_COUNT)
        return int(count) if isinstance(count, (int, str)) else 0

    async def get_connections_count(self) -> int:
        """Obtiene el número de conexiones activas."""
        value = await self.get(RedisKeys.SERVER_CONNECTIONS_COUNT)
        return int(value) if value is not None else 0

    # ── Player sessions ────────────────────────────────────────────────

    async def set_player_session(self, user_id: int, data: dict[str, Any]) -> None:
        """Establece la sesión de un jugador."""
        key = RedisKeys.session_active(user_id)
        await self.hset(key, {k: str(v) for k, v in data.items()})
        logger.info("Sesión establecida para jugador %d", user_id)

    async def get_player_session(self, user_id: int) -> dict[str, str]:
        """Obtiene la sesión de un jugador."""
        key = RedisKeys.session_active(user_id)
        return await self.hgetall(key)

    async def delete_player_session(self, user_id: int) -> None:
        """Elimina la sesión de un jugador."""
        key = RedisKeys.session_active(user_id)
        await self.delete(key)
        logger.info("Sesión eliminada para jugador %d", user_id)

    async def update_player_last_seen(self, user_id: int) -> None:
        """Actualiza el timestamp de último acceso de un jugador."""
        key = RedisKeys.session_last_seen(user_id)
        await self.set(key, str(int(time.time())))

    # ── Active merchant sessions ───────────────────────────────────────

    async def get_active_merchant(self, user_id: int) -> int | None:
        """Obtiene el NPC ID del mercader activo para un jugador."""
        value = await self.get(RedisKeys.session_active_merchant(user_id))
        if value is None:
            return None
        try:
            return int(value)
        except ValueError, TypeError:
            return None

    async def set_active_merchant(self, user_id: int, npc_id: int) -> None:
        """Establece el mercader activo para un jugador."""
        key = RedisKeys.session_active_merchant(user_id)
        await self.set(key, str(npc_id))

    async def delete_active_merchant(self, user_id: int) -> None:
        """Elimina el mercader activo para un jugador."""
        key = RedisKeys.session_active_merchant(user_id)
        await self.delete(key)
