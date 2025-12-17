"""Handler especializado para autenticación y validaciones de login."""

import asyncio
import logging
from typing import TYPE_CHECKING

from src.services.player.authentication_service import AuthenticationService

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class LoginAuthenticationHandler:
    """Handler especializado para autenticación y validaciones de login."""

    def __init__(
        self,
        player_repo: PlayerRepository | None,
        account_repo: AccountRepository | None,
        map_manager: MapManager | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de autenticación.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

    def validate_repositories(self) -> bool:
        """Valida que los repositorios necesarios estén disponibles.

        Returns:
            True si están disponibles, False en caso contrario.
        """
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para login")
            # Enviar error al cliente (fire and forget)
            task = asyncio.create_task(self.message_sender.send_error_msg("Servicio no disponible"))
            task.add_done_callback(lambda _: None)  # Evitar warning de task no awaited
            return False
        return True

    def is_user_already_connected(self, username: str) -> bool:
        """Verifica si el usuario ya tiene una sesión activa.

        Args:
            username: Nombre de usuario.

        Returns:
            True si el usuario ya está conectado, False en caso contrario.
        """
        if not self.map_manager:
            return False

        # Verificar si el username ya está en algún mapa
        existing_user_id = self.map_manager.find_player_by_username(username)
        return existing_user_id is not None

    async def authenticate_user(self, username: str, password: str) -> tuple[int, int] | None:
        """Autentica al usuario.

        Args:
            username: Nombre de usuario.
            password: Contraseña.

        Returns:
            Tupla (user_id, user_class) si la autenticación es exitosa, None en caso contrario.
        """
        if not self.account_repo:
            return None

        auth_service = AuthenticationService(self.account_repo, self.message_sender)
        return await auth_service.authenticate(username, password)
