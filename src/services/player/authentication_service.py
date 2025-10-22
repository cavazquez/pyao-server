"""Servicio para autenticación de usuarios."""

import logging
from typing import TYPE_CHECKING

from src.utils.password_utils import hash_password

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Servicio que encapsula la lógica de autenticación de usuarios."""

    def __init__(
        self,
        account_repo: AccountRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el servicio de autenticación.

        Args:
            account_repo: Repositorio de cuentas.
            message_sender: Enviador de mensajes al cliente.
        """
        self.account_repo = account_repo
        self.message_sender = message_sender

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> tuple[int, int] | None:
        """Autentica un usuario y devuelve sus datos si es exitoso.

        Encapsula toda la lógica de autenticación:
        - Verificar que los repositorios estén disponibles
        - Obtener datos de la cuenta
        - Verificar contraseña
        - Enviar mensajes de error al cliente si falla

        Args:
            username: Nombre de usuario.
            password: Contraseña en texto plano.

        Returns:
            Tupla (user_id, user_class) si la autenticación es exitosa.
            None si falla (ya envió el error al cliente).
        """
        logger.info(
            "Intento de autenticación desde %s - Username: %s",
            self.message_sender.connection.address,
            username,
        )

        # Verificar que el repositorio esté disponible
        if self.account_repo is None:
            logger.error("Repositorio de cuentas no está disponible")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return None

        # Obtener datos de la cuenta
        account_data = await self.account_repo.get_account(username)
        if not account_data:
            logger.warning("Intento de login con usuario inexistente: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return None

        # Hashear la contraseña para compararla
        password_hash = hash_password(password)
        if not await self.account_repo.verify_password(username, password_hash):
            logger.warning("Contraseña incorrecta para usuario: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return None

        # Autenticación exitosa
        user_id = int(account_data.get("user_id", 0))
        user_class = int(account_data.get("char_job", 1))
        logger.info(
            "Autenticación exitosa para %s (ID: %d, Clase: %d)",
            username,
            user_id,
            user_class,
        )

        return (user_id, user_class)
