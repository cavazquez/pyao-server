"""Cliente Redis singleton para el servidor."""

import logging
import time
from typing import Any, Self, cast

import redis.asyncio as redis

from src.redis_config import DEFAULT_SERVER_CONFIG, RedisConfig, RedisKeys

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

        for key, value in DEFAULT_SERVER_CONFIG.items():
            # Solo establecer si no existe
            exists = await self._redis.exists(key)
            if not exists:
                await self._redis.set(key, value)
                logger.info("Configuración inicializada: %s = %s", key, value)

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

    # Métodos para gestión de cuentas

    async def account_exists(self, username: str) -> bool:
        """Verifica si existe una cuenta con el username dado.

        Args:
            username: Nombre de usuario a verificar.

        Returns:
            True si la cuenta existe, False en caso contrario.
        """
        key = RedisKeys.account_id_by_username(username)
        return bool(await self.redis.exists(key))

    async def create_account(
        self,
        username: str,
        password_hash: str,
        email: str,
        char_data: dict[str, Any] | None = None,
    ) -> int:
        """Crea una nueva cuenta de usuario.

        Args:
            username: Nombre de usuario.
            password_hash: Hash de la contraseña.
            email: Email del usuario.
            char_data: Datos opcionales del personaje (job, race, gender, home, head).

        Returns:
            ID del usuario creado.

        Raises:
            ValueError: Si la cuenta ya existe.
        """
        # Verificar si la cuenta ya existe
        if await self.account_exists(username):
            msg = f"La cuenta '{username}' ya existe"
            raise ValueError(msg)

        # Generar nuevo user_id
        user_id = await self.redis.incr(RedisKeys.ACCOUNTS_COUNTER)
        user_id = int(user_id) if isinstance(user_id, (int, str)) else 0

        # Guardar mapeo username -> user_id
        username_key = RedisKeys.account_id_by_username(username)
        await self.redis.set(username_key, str(user_id))

        # Guardar datos de la cuenta
        account_key = RedisKeys.account_data(username)
        account_data = {
            "user_id": str(user_id),
            "username": username,
            "password_hash": password_hash,
            "email": email,
            "created_at": str(int(time.time())),
        }

        # Agregar datos del personaje si están presentes
        if char_data:
            for key, value in char_data.items():
                account_data[f"char_{key}"] = str(value)

        await self.redis.hset(account_key, mapping=account_data)  # type: ignore[misc]

        logger.info("Cuenta creada: %s (ID: %d)", username, user_id)
        return user_id

    async def get_account_data(self, username: str) -> dict[str, str]:
        """Obtiene los datos de una cuenta.

        Args:
            username: Nombre de usuario.

        Returns:
            Diccionario con los datos de la cuenta.
        """
        key = RedisKeys.account_data(username)
        result: dict[str, str] = await self.redis.hgetall(key)  # type: ignore[misc]
        return result

    async def get_user_id_by_username(self, username: str) -> int | None:
        """Obtiene el user_id asociado a un username.

        Args:
            username: Nombre de usuario.

        Returns:
            ID del usuario o None si no existe.
        """
        key = RedisKeys.account_id_by_username(username)
        value = await self.redis.get(key)
        return int(value) if value is not None else None
