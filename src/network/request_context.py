"""Contexto de una petición; nunca se comparte el emisor entre conexiones."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.network.session_manager import SessionManager

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

type SessionState = dict[str, dict[str, int] | int | str]


@dataclass(frozen=True)
class RequestContext:
    """El emisor pertenece a la conexión y el diccionario a su sesión mutable."""

    sender: MessageSender
    session: SessionState | None

    @property
    def user_id(self) -> int | None:
        """Consulta el usuario actual, sin cachearlo antes de completar el login."""
        return SessionManager.get_user_id(self.session)
