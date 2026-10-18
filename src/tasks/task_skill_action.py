"""Petición optativa, acotada e idempotente de acciones de habilidades."""

import json
from typing import TYPE_CHECKING, Any

from src.network.capabilities import Capability
from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task
from src.utils.gold_atomic import validate_operation_id

MIN_REQUEST_BYTES = 4


if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.services.skill_action_service import SkillActionService

MAX_REQUEST_BYTES = 1024
MAX_REPLY_BYTES = 3800
ACTION_FIELDS: dict[str, dict[str, type]] = {
    "hide": {},
    "navigate": {"slot": int},
    "attack": {"x": int, "y": int},
    "work": {"skill": int, "x": int, "y": int},
    "craft": {"recipe": str, "quantity": int},
    "recipes": {"skill": str, "page": int},
}


class TaskSkillAction(Task):
    """No admite valores de progreso o inventario suministrados por el cliente."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        skill_actions: SkillActionService | None = None,
        session_data: dict[str, int | dict[str, int]] | None = None,
    ) -> None:
        """Recibe sólo la sesión autenticada y el servicio compartido."""
        super().__init__(data, message_sender)
        self.skill_actions, self.session_data = skill_actions, session_data or {}

    async def execute(self) -> None:
        """Valida esquema y capacidad antes de invocar una acción."""
        connection = self.message_sender.connection
        user = SessionManager.get_user_id(self.session_data)
        if (
            not user
            or self.skill_actions is None
            or not connection.is_authenticated
            or not connection.capabilities.enabled & Capability.SKILL_ACTIONS
        ):
            return
        if len(self.data) > MAX_REQUEST_BYTES or len(self.data) < MIN_REQUEST_BYTES:
            return
        identity = ""
        try:
            reader = PacketReader(self.data)
            if reader.read_byte() != 1:
                return
            request = json.loads(reader.read_ascii_string())
            if (
                reader.offset != len(self.data)
                or type(request) is not dict
                or set(request) != {"id", "action", "params"}
            ):
                return
            identity = request["id"]
            validate_operation_id(identity)
            action, params = request["action"], request["params"]
            if type(action) is not str or action not in ACTION_FIELDS or type(params) is not dict:
                return
            fields = ACTION_FIELDS[action]
            if set(params) != set(fields) or any(
                type(params[k]) is not kind for k, kind in fields.items()
            ):
                return
            result = await self.skill_actions.execute(
                user, action, params, self.message_sender, identity=identity, announce=False
            )
        except (ValueError, TypeError, KeyError, IndexError) as error:
            result = {"applied": False, "message": str(error)[:160]}
        await self._reply(identity, result)

    async def _reply(self, identity: str, result: dict[str, Any]) -> None:
        text = json.dumps({"id": identity, **result}, ensure_ascii=True, separators=(",", ":"))
        if len(text) > MAX_REPLY_BYTES:
            text = json.dumps(
                {"id": identity, "applied": False, "message": "Respuesta demasiado extensa."}
            )
        await self.message_sender.connection.send(
            PacketBuilder()
            .add_byte(ServerPacketID.SKILL_ACTION_STATE)
            .add_byte(1)
            .add_unicode_string(text)
            .to_bytes()
        )
