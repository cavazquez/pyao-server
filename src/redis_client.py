"""Cliente Redis singleton para el servidor."""

import logging
import time
from typing import Any, Self, cast

import redis.asyncio as redis

from src.redis_config import DEFAULT_EFFECTS_CONFIG, DEFAULT_SERVER_CONFIG, RedisConfig, RedisKeys

logger = logging.getLogger(__name__)


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
            # Verificar conexión
            await self._redis.ping()
            logger.info("Conectado a Redis en %s:%d", config.host, config.port)

            # Inicializar configuración por defecto si no existe
            await self._initialize_default_config()

        except redis.ConnectionError as e:
            logger.warning(
                "No se pudo conectar a Redis en %s:%d - %s",
                config.host,
                config.port,
                e,
            )
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

        # Inicializar configuración del servidor
        for key, value in DEFAULT_SERVER_CONFIG.items():
            exists = await self._redis.exists(key)
            if not exists:
                await self._redis.set(key, value)
                logger.info("Configuración inicializada: %s = %s", key, value)

        # Inicializar configuración de efectos del juego
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
    def redis(self) -> redis.Redis:
        """Retorna la instancia de Redis.

        Returns:
            Instancia de Redis.

        Raises:
            RuntimeError: Si Redis no está conectado.
        """
        if self._redis is None:
            msg = "Redis no está conectado. Llama a connect() primero."
            raise RuntimeError(msg)
        return self._redis

    # Métodos de conveniencia para configuración del servidor

    async def get_server_host(self) -> str:
        """Obtiene el host del servidor desde Redis.

        Returns:
            Host del servidor.
        """
        value = await self.redis.get(RedisKeys.CONFIG_SERVER_HOST)
        return value if value is not None else "0.0.0.0"

    async def get_server_port(self) -> int:
        """Obtiene el puerto del servidor desde Redis.

        Returns:
            Puerto del servidor.
        """
        value = await self.redis.get(RedisKeys.CONFIG_SERVER_PORT)
        return int(value) if value is not None else 7666

    async def set_server_host(self, host: str) -> None:
        """Establece el host del servidor en Redis."""
        await self.redis.set(RedisKeys.CONFIG_SERVER_HOST, host)
        logger.info("Host del servidor actualizado: %s", host)

    async def set_server_port(self, port: int) -> None:
        """Establece el puerto del servidor en Redis."""
        await self.redis.set(RedisKeys.CONFIG_SERVER_PORT, str(port))
        logger.info("Puerto del servidor actualizado: %d", port)

    # Métodos para gestión de conexiones

    async def increment_connections(self) -> int:
        """Incrementa el contador de conexiones activas.

        Returns:
            Número actual de conexiones activas.
        """
        count = await self.redis.incr(RedisKeys.SERVER_CONNECTIONS_COUNT)
        return int(count) if isinstance(count, (int, str)) else 0

    async def decrement_connections(self) -> int:
        """Decrementa el contador de conexiones activas.

        Returns:
            Número actual de conexiones activas.
        """
        count = await self.redis.decr(RedisKeys.SERVER_CONNECTIONS_COUNT)
        return int(count) if isinstance(count, (int, str)) else 0

    async def get_connections_count(self) -> int:
        """Obtiene el número de conexiones activas.

        Returns:
            Número de conexiones activas.
        """
        value = await self.redis.get(RedisKeys.SERVER_CONNECTIONS_COUNT)
        return int(value) if value is not None else 0

    # Métodos para gestión de sesiones de jugadores

    async def set_player_session(self, user_id: int, data: dict[str, Any]) -> None:
        """Establece la sesión de un jugador.

        Args:
            user_id: ID del jugador.
            data: Datos de la sesión.
        """
        key = RedisKeys.session_active(user_id)
        await self.redis.hset(key, mapping=data)  # type: ignore[misc]
        logger.info("Sesión establecida para jugador %d", user_id)

    async def get_player_session(self, user_id: int) -> dict[str, str]:
        """Obtiene la sesión de un jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Datos de la sesión.
        """
        key = RedisKeys.session_active(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)  # type: ignore[misc]
        return result

    async def delete_player_session(self, user_id: int) -> None:
        """Elimina la sesión de un jugador.

        Args:
            user_id: ID del jugador.
        """
        key = RedisKeys.session_active(user_id)
        await self.redis.delete(key)
        logger.info("Sesión eliminada para jugador %d", user_id)

    async def update_player_last_seen(self, user_id: int) -> None:
        """Actualiza el timestamp de último acceso de un jugador.

        Args:
            user_id: ID del jugador.
        """
        key = RedisKeys.session_last_seen(user_id)
        await self.redis.set(key, str(int(time.time())))

    # NOTA: Los métodos de gestión de cuentas, jugadores, servidor y configuración
    # de efectos fueron movidos a AccountRepository, PlayerRepository y ServerRepository.
    # RedisClient ahora solo maneja operaciones de bajo nivel: conexión,
    # configuración del servidor y contadores de sesiones.
