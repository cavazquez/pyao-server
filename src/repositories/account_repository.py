"""Repositorio para operaciones de cuentas de usuario usando Redis."""

import logging
from typing import TYPE_CHECKING

from src.utils.password_utils import verify_password as verify_password_hash
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object

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
            "is_gm": "0",  # Por defecto no es GM
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

    async def verify_password(self, username: str, password: str) -> bool:
        """Verifica si la contraseña es correcta.

        Args:
            username: Nombre de usuario.
            password: Contraseña en texto plano enviada por el cliente.

        Returns:
            True si la contraseña es correcta, False en caso contrario.
        """
        account_data = await self.get_account(username)

        if account_data is None:
            return False

        stored_hash = account_data.get("password_hash", "")
        return verify_password_hash(password, stored_hash)

    async def is_gm(self, username: str) -> bool:
        """Verifica si un usuario es Game Master.

        Args:
            username: Nombre de usuario.

        Returns:
            True si el usuario es GM, False en caso contrario.
        """
        account_data = await self.get_account(username)
        if not account_data:
            return False

        is_gm_str = account_data.get("is_gm", "0")
        return is_gm_str == "1"

    async def set_gm_status(self, username: str, is_gm: bool) -> None:
        """Establece el estado de GM de un usuario.

        Args:
            username: Nombre de usuario.
            is_gm: True para hacer GM, False para quitar GM.
        """
        account_key = RedisKeys.account_data(username)
        await self.redis.redis.hset(account_key, "is_gm", "1" if is_gm else "0")  # type: ignore[misc]
        logger.info("Estado GM actualizado para %s: %s", username, "GM" if is_gm else "No GM")

    async def get_account_by_user_id(self, user_id: int) -> dict[str, str] | None:
        """Obtiene los datos de una cuenta por user_id.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con los datos de la cuenta o None si no existe.
        """
        # Buscar en todas las cuentas (esto es ineficiente, pero funcional por ahora)
        # En el futuro, podríamos mantener un índice user_id -> username en Redis
        # Por ahora, iteramos sobre las claves de cuentas
        pattern = "account:*:data"
        keys = await self.redis.redis.keys(pattern)
        logger.debug("Buscando cuenta para user_id=%d, encontradas %d claves", user_id, len(keys))

        for key in keys:
            account_data: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]
            account_user_id_str = account_data.get("user_id")
            if account_user_id_str == str(user_id):
                logger.debug("Cuenta encontrada para user_id=%d en key=%s", user_id, key)
                return account_data

        logger.warning(
            "No se encontró cuenta para user_id=%d después de revisar %d claves", user_id, len(keys)
        )
        return None

    async def is_gm_by_user_id(self, user_id: int) -> bool:
        """Verifica si un usuario es Game Master por user_id.

        Args:
            user_id: ID del usuario.

        Returns:
            True si el usuario es GM, False en caso contrario.
        """
        account_data = await self.get_account_by_user_id(user_id)
        if not account_data:
            logger.warning("No se encontró cuenta para user_id=%d al verificar GM", user_id)
            return False

        is_gm_str_raw = account_data.get("is_gm", "0")
        # Limpiar espacios y saltos de línea (por si Redis tiene caracteres extra)
        is_gm_str = is_gm_str_raw.strip() if is_gm_str_raw else "0"
        result = is_gm_str == "1"
        logger.debug(
            "Verificación GM para user_id=%d: is_gm_str='%s' (después de strip), resultado=%s",
            user_id,
            is_gm_str,
            result,
        )
        return result
