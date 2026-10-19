"""Serialización reentrante de mutaciones sociales y sus snapshots."""

import asyncio
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import TracebackType


class GroupLock:
    """Una operación puede consultar su propia fachada sin bloquearse a sí misma."""

    def __init__(self) -> None:
        """Crea una reserva local al servidor, sin estado global entre instancias."""
        self.lock = asyncio.Lock()
        self.owner: asyncio.Task[Any] | None = None
        self.depth = 0

    async def __aenter__(self) -> None:
        """Adquiere la reserva o aumenta la profundidad de su propietario."""
        task = asyncio.current_task()
        if task is not self.owner:
            await self.lock.acquire()
            self.owner = task
        self.depth += 1

    async def __aexit__(
        self,
        _kind: type[BaseException] | None,
        _error: BaseException | None,
        _trace: TracebackType | None,
    ) -> None:
        """Libera la reserva incluso ante error o cancelación."""
        self.depth -= 1
        if not self.depth:
            self.owner = None
            self.lock.release()


def serialized[**P, R](
    function: Callable[P, Awaitable[R]], lock: GroupLock
) -> Callable[P, Awaitable[R]]:
    """Conserva la firma pública y serializa llamadas legacy y estructuradas.

    Returns:
        Operación con el mismo resultado y orden de efectos.
    """

    @wraps(function)
    async def execute(*args: P.args, **kwargs: P.kwargs) -> R:
        async with lock:
            return await function(*args, **kwargs)

    return execute


def bind_groups(party: object, clan: object, lock: GroupLock) -> None:
    """Comparte la reserva entre fachadas y consultas del estado social."""
    for service, names in (
        (
            party,
            (
                "create_party",
                "invite_to_party",
                "accept_invitation",
                "leave_party",
                "kick_member",
                "transfer_leadership",
                "get_party_info",
                "get_user_invitations",
                "send_party_message",
                "distribute_experience",
                "update_member_level",
                "set_member_online_status",
            ),
        ),
        (
            clan,
            (
                "create_clan",
                "invite_to_clan",
                "accept_invitation",
                "reject_invitation",
                "leave_clan",
                "kick_member",
                "promote_member",
                "demote_member",
                "transfer_leadership",
                "send_clan_message",
            ),
        ),
    ):
        for name in names:
            setattr(service, name, serialized(getattr(service, name), lock))
