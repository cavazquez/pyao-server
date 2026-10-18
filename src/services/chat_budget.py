"""Token bucket compartido por jugador para todos los canales de conversación."""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

from src.network.packet_id import ClientPacketID

CHAT_FIELDS: dict[int, int] = {
    ClientPacketID.TALK: 1,
    ClientPacketID.YELL: 1,
    ClientPacketID.WHISPER: 2,
    ClientPacketID.PARTY_MESSAGE: 1,
}
ESSENTIAL_TALK = {"/METRICS", "/SALIRCLAN", "/RECHAZARCLAN", "/LIBERAR"}
BURST = 5.0
REFILL_PER_SECOND = 1.0
MAX_MESSAGE_BYTES = 512
MAX_USERS = 10000
IDLE_SECONDS = 300.0
PRUNE_SECONDS = 60.0
WARNING_SECONDS = 5.0


@dataclass
class Bucket:
    """No conserva mensajes, nombres ni secretos, sólo presupuesto temporal."""

    tokens: float
    updated: float
    warning_at: float


class ChatBudget:
    """No espera ni bloquea otros jugadores; la reconexión conserva el presupuesto."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        """Permite simular reposición y expiración sin sleeps."""
        self.clock = clock
        self._users: dict[int, Bucket] = {}
        self._prune_at = clock() + PRUNE_SECONDS

    @staticmethod
    def _message(data: bytes) -> str | None:
        offset = 1
        message = ""
        for _ in range(CHAT_FIELDS[data[0]]):
            if len(data) < offset + 2:
                return None
            length = int.from_bytes(data[offset : offset + 2], "little")
            offset += 2
            if len(data) < offset + length:
                return None
            message = data[offset : offset + length].decode("latin-1")
            offset += length
        return message if offset == len(data) else None

    def gate(self, user_id: int, data: bytes) -> tuple[bool, bool] | None:
        """Decide antes de crear handlers; el segundo bool autoriza un aviso acotado.

        Returns:
            (permitido, avisar), o None para paquetes fuera del chat.
        """
        if not data or data[0] not in CHAT_FIELDS:
            return None
        message = self._message(data)
        if message is None:
            return False, False
        within_size = len(message.encode("latin-1")) <= MAX_MESSAGE_BYTES
        words = message.split(maxsplit=1)
        essential = (
            data[0] == ClientPacketID.TALK
            and message.startswith("/")
            and bool(words)
            and words[0].upper() in ESSENTIAL_TALK
        )
        if within_size and essential:
            return True, False
        now = self.clock()
        if now >= self._prune_at:
            self._users = {
                user: state
                for user, state in self._users.items()
                if now - state.updated < IDLE_SECONDS
            }
            self._prune_at = now + PRUNE_SECONDS
        state = self._users.get(user_id)
        if state is None:
            if len(self._users) >= MAX_USERS:
                return False, False
            state = Bucket(BURST, now, now)
            self._users[user_id] = state
        state.tokens = min(BURST, state.tokens + max(0.0, now - state.updated) * REFILL_PER_SECOND)
        state.updated = now
        if within_size and state.tokens >= 1.0:
            state.tokens -= 1.0
            return True, False
        notify = now >= state.warning_at
        if notify:
            state.warning_at = now + WARNING_SECONDS
        return False, notify
