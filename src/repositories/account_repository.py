"""Repositorio para operaciones de cuentas de usuario usando Redis."""

import logging
from typing import TYPE_CHECKING

from src.repositories.account_creation import create_indexed_account
from src.security.password_executor import get_password_executor
from src.utils.password_utils import verify_password as verify_password_hash
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object

logger = logging.getLogger(__name__)
USER_ACCOUNT_INDEX = "account:index:user_id"
USER_ACCOUNT_INDEX_STATE = "account:index:progress"


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

        """
        account_data = {"password_hash": password_hash, "email": email}

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

        user_id = await create_indexed_account(self.redis.redis, username, account_data)
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
        result: dict[str, str] = await self.redis.hgetall(account_key)

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
        if not await get_password_executor().run(verify_password_hash, password, stored_hash):
            return False
        # La credencial no puede haber cambiado durante el trabajo de Argon2.
        current = await self.get_account(username)
        return current is not None and current.get("password_hash", "") == stored_hash

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
        await self.redis.hset(account_key, "is_gm", "1" if is_gm else "0")
        logger.info("Estado GM actualizado para %s: %s", username, "GM" if is_gm else "No GM")

    async def get_account_by_user_id(self, user_id: int) -> dict[str, str] | None:
        """Obtiene los datos de una cuenta por user_id.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con los datos de la cuenta o None si no existe.
        """
        username = await self.redis.hget(USER_ACCOUNT_INDEX, str(user_id))
        if not username:
            return None
        account = await self.get_account(str(username))
        if not account or account.get("user_id") != str(user_id):
            return None
        return account

    async def backfill_user_index(self, batch_size: int = 128) -> None:
        """Completa el índice por lotes reanudables.

        Raises:
            ValueError: Si los mapeos existentes contienen identidades contradictorias.
        """
        state = await self.redis.hgetall(USER_ACCOUNT_INDEX_STATE)
        if state.get("complete") == "1":
            return
        cursor = int(state.get("cursor", 0))
        while True:
            cursor, keys = await self.redis.redis.scan(
                cursor, match="account:*:data", count=batch_size
            )
            for key in keys:
                name = key.decode() if isinstance(key, bytes) else key
                account = await self.redis.hgetall(name)
                user_id, username = account.get("user_id", ""), account.get("username", "")
                if not user_id.isdigit() or int(user_id) < 1 or not username:
                    message = "Cuenta heredada sin identidad válida; se conserva para revisión"
                    raise ValueError(message)
                reverse = await self.redis.get(RedisKeys.account_id_by_username(username))
                if name != RedisKeys.account_data(username) or str(reverse) != user_id:
                    message = "Mapeos de cuenta contradictorios; el índice no se sobrescribe"
                    raise ValueError(message)
                await self.redis.redis.hsetnx(USER_ACCOUNT_INDEX, user_id, username)
                if await self.redis.hget(USER_ACCOUNT_INDEX, user_id) != username:
                    message = "Dos cuentas declaran el mismo user_id"
                    raise ValueError(message)
            await self.redis.hset(
                USER_ACCOUNT_INDEX_STATE,
                mapping={"cursor": str(cursor), "complete": "1" if cursor == 0 else "0"},
            )
            if cursor == 0:
                return

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
