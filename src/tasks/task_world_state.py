"""Acciones de interfaz optativas, limitadas por conexión y por revisión de estado."""

import json
from time import monotonic
from typing import TYPE_CHECKING

from src.network.capabilities import Capability
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.network.state_channel import send_state
from src.services.expansion.service import EXPANSION_TOPICS
from src.services.world.actions import ACTION_FIELDS
from src.tasks.task import Task
from src.utils.gold_atomic import validate_operation_id

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.world.world_state import WorldStateService

MIN_REQUEST_BYTES = 4
MAX_REQUEST_BYTES = 1024
BURST = 8.0
REFILL_PER_SECOND = 4.0
MAX_TEXT_LENGTH = 200
MAX_EPOCH_LENGTH = 32
MAX_REVISION_LENGTH = 64


class TaskWorldState(Task):
    """La identidad del actor proviene únicamente de SessionManager."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        world_state: WorldStateService | None = None,
        session_data: dict[str, int | dict[str, int]] | None = None,
    ) -> None:
        """Recibe el servicio compartido y la sesión autenticada."""
        super().__init__(data, message_sender)
        self.world_state = world_state
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Valida exactamente campos, tipos, capacidad y presupuesto antes de leer estado."""
        connection = self.message_sender.connection
        user = SessionManager.get_user_id(self.session_data)
        if (
            not user
            or self.world_state is None
            or not connection.is_authenticated
            or not connection.capabilities.enabled & Capability.WORLD_STATE
        ):
            return
        now = monotonic()
        connection.state_tokens = min(
            BURST,
            connection.state_tokens + max(0, now - connection.state_budget_at) * REFILL_PER_SECOND,
        )
        connection.state_budget_at = now
        if (
            connection.state_tokens < 1
            or not MIN_REQUEST_BYTES <= len(self.data) <= MAX_REQUEST_BYTES
        ):
            return
        connection.state_tokens -= 1
        identity = ""
        try:
            reader = PacketReader(self.data)
            if reader.read_byte() != 1:
                return
            request = json.loads(reader.read_ascii_string())
            if (
                type(request) is not dict
                or set(request) != {"id", "epoch", "revision", "action", "params"}
                or reader.offset != len(self.data)
            ):
                return
            identity = request["id"]
            if (
                type(identity) is not str
                or any(type(request[field]) is not str for field in ("epoch", "revision", "action"))
                or len(request["epoch"]) > MAX_EPOCH_LENGTH
                or len(request["revision"]) > MAX_REVISION_LENGTH
            ):
                return
            validate_operation_id(identity)
            action, params = request["action"], request["params"]
            if (
                type(action) is str
                and action.split(".")[0] in EXPANSION_TOPICS
                and not connection.capabilities.enabled & Capability.EXPANSION
            ):
                return
            if action not in ACTION_FIELDS or type(params) is not dict:
                return
            fields = ACTION_FIELDS[action]
            if (
                set(params) != set(fields)
                or any(type(params[key]) is not kind for key, kind in fields.items())
                or any(
                    isinstance(value, str) and len(value) > MAX_TEXT_LENGTH
                    for value in params.values()
                )
            ):
                return
            await self.world_state.execute(user, self.message_sender, request)
        except (ValueError, TypeError, KeyError, IndexError) as error:
            await send_state(
                self.message_sender,
                "result",
                {"applied": False, "message": str(error)[:160]},
                identity=identity,
            )
