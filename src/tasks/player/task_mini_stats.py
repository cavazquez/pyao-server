"""Solicitud autenticada de contadores propios y condena restante."""

from typing import TYPE_CHECKING

from src.network.session_manager import SessionManager
from src.services.player.lifetime_stats import mini_stats_packet
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository


class TaskMiniStats(Task):
    """Sólo permite consultar el personaje autenticado de esta conexión."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Conserva repositorios y contexto de la conexión."""
        super().__init__(data, message_sender)
        self.player = player_repo
        self.account = account_repo
        self.session_data = session_data

    async def execute(self) -> None:
        """Devuelve el snapshot actual sin aceptar un ID de usuario del cliente."""
        user = SessionManager.get_user_id(self.session_data)
        if user is not None and not isinstance(user, dict):
            await self.message_sender.connection.send(
                await mini_stats_packet(self.player, self.account, int(user))
            )
