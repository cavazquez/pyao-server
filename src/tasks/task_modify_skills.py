"""Petición optativa con ID del servidor y 22 pares ID/delta, nunca valores absolutos."""

import struct
from typing import TYPE_CHECKING

from src.models.skills import CATALOG
from src.network.capabilities import Capability
from src.network.session_manager import SessionManager
from src.services.skill_allocation import (
    MAX_OPERATION_ID_BYTES,
    allocate_skill_points,
    send_allocation_state,
)
from src.tasks.task import Task
from src.utils.gold_atomic import validate_operation_id

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

PAIR_BYTES = 3
REQUEST_HEADER_BYTES = 4


class TaskModifySkills(Task):
    """Aísla autenticación, versión y parsing de la transacción de progreso."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository,
        session_data: dict[str, int | dict[str, int]] | None = None,
    ) -> None:
        """Recibe la cuenta actual mediante la factory habitual."""
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data if session_data is not None else {}

    async def execute(self) -> None:
        """Descarta pedidos sin autenticación/capacidad y responde con estado autoritativo."""
        user_id = SessionManager.get_user_id(self.session_data)
        connection = self.message_sender.connection
        if (
            not user_id
            or not connection.is_authenticated
            or not connection.capabilities.enabled & Capability.SKILL_ALLOCATION
        ):
            return
        if len(self.data) < REQUEST_HEADER_BYTES or self.data[1] != 1:
            return
        length = int.from_bytes(self.data[2:4], "little")
        if length > MAX_OPERATION_ID_BYTES or len(self.data) != 4 + length + PAIR_BYTES * len(
            CATALOG
        ):
            return
        identity = ""
        try:
            candidate = self.data[4 : 4 + length].decode("ascii")
            validate_operation_id(candidate)
            identity = candidate
            deltas = tuple(
                struct.unpack_from("<Bh", self.data, 4 + length + PAIR_BYTES * index)
                for index in range(len(CATALOG))
            )
            result = await allocate_skill_points(
                self.player_repo.redis.redis, user_id, identity, deltas
            )
        except (ValueError, UnicodeDecodeError) as error:
            await send_allocation_state(
                self.message_sender,
                self.player_repo,
                user_id,
                identity=identity,
                status=2,
                message=str(error),
            )
        else:
            await send_allocation_state(
                self.message_sender,
                self.player_repo,
                user_id,
                identity=identity,
                status=1 if result["applied"] else 2,
                message=str(result["message"]),
            )
