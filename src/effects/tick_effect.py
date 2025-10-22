"""Clase base abstracta para efectos de tick del juego."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository


class TickEffect(ABC):
    """Clase base abstracta para efectos de tick."""

    @abstractmethod
    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica el efecto a un jugador.

        Args:
            user_id: ID del usuario.
            player_repo: Repositorio de jugadores.
            message_sender: MessageSender del jugador (puede ser None).
        """

    @abstractmethod
    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto."""

    @abstractmethod
    def get_name(self) -> str:
        """Retorna el nombre del efecto para logging."""
