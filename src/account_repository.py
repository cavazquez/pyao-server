"""Repositorio para operaciones de cuentas de usuario usando Redis."""

import logging
from typing import TYPE_CHECKING

from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class AccountRepository:
    """Repositorio para operaciones de cuentas de usuario."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio.

        Args:
            redis_client: Cliente Redis para operaciones de bajo nivel.
        """
        self.redis = redis_client

    async def create_account(
        self, username: str, password_hash: str, email: str, char_data: dict[str, int] | None = None
    ) -> int:
        """Crea una nueva cuenta de usuario.

        Args:
            username: Nombre de usuario.
            password_hash: Hash de la contraseña.
            email: Email del usuario.
            char_data: Datos del personaje (race, gender, job, head, home).

        Returns:
            ID del usuario creado.

        Raises:
            ValueError: Si la cuenta ya existe.
        """
        # Verificar si el usuario ya existe
        username_key = RedisKeys.account_id_by_username(username)
        existing_id = await self.redis.redis.get(username_key)

        if existing_id is not None:
            msg = f"La cuenta '{username}' ya existe"
            raise ValueError(msg)

        # Generar nuevo user_id
        user_id = int(await self.redis.redis.incr(RedisKeys.ACCOUNTS_COUNTER))

        # Guardar mapeo username -> user_id
        await self.redis.redis.set(username_key, str(user_id))

        # Guardar datos de la cuenta
        account_key = RedisKeys.account_data(username)
        account_data = {
            "user_id": str(user_id),
            "username": username,
            "password_hash": password_hash,
            "email": email,
        }

        # Agregar datos del personaje si existen
        if char_data:
            account_data.update(
                {
                    "char_race": str(char_data.get("race", 1)),
                    "char_gender": str(char_data.get("gender", 1)),
                    "char_job": str(char_data.get("job", 1)),
                    "char_head": str(char_data.get("head", 1)),
                    "char_home": str(char_data.get("home", 1)),
                }
            )

        await self.redis.redis.hset(account_key, mapping=account_data)  # type: ignore[misc]
        logger.info("Cuenta creada: %s (ID: %d)", username, user_id)

        return user_id

    async def get_account(self, username: str) -> dict[str, str] | None:
        """Obtiene los datos de una cuenta.

        Args:
            username: Nombre de usuario.

        Returns:
            Diccionario con los datos de la cuenta o None si no existe.
        """
        account_key = RedisKeys.account_data(username)
        result: dict[str, str] = await self.redis.redis.hgetall(account_key)  # type: ignore[misc]

        if not result:
            return None

        return result

    async def verify_password(self, username: str, password_hash: str) -> bool:
        """Verifica si la contraseña es correcta.

        Args:
            username: Nombre de usuario.
            password_hash: Hash de la contraseña a verificar.

        Returns:
            True si la contraseña es correcta, False en caso contrario.
        """
        account_data = await self.get_account(username)

        if account_data is None:
            return False

        stored_hash = account_data.get("password_hash", "")
        return stored_hash == password_hash
