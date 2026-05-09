"""Task para mover items dentro del inventario del jugador."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.commands.move_item_command import MoveItemCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

MIN_PACKET_LENGTH = 3

if TYPE_CHECKING:
    from src.command_handlers.move_item_handler import MoveItemCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskMoveItem(Task):
    """Mueve un item de un slot a otro del inventario.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        move_item_handler: MoveItemCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Crea la task con sus dependencias opcionales.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            move_item_handler: Handler para el comando de mover item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.move_item_handler = move_item_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Mueve item si los datos y la sesión son válidos (solo parsing y delegación)."""
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning("Intento de mover item sin usuario logueado")
            return

        old_slot, new_slot = self._parse_payload(self.data)

        if old_slot is None or new_slot is None:
            logger.warning("Packet MOVE_ITEM inválido: falta información de slots")
            return

        if not self.move_item_handler:
            logger.error("MoveItemCommandHandler no disponible")
            return

        command = MoveItemCommand(
            user_id=user_id,
            old_slot=old_slot,
            new_slot=new_slot,
        )

        result = await self.move_item_handler.handle(command)

        if not result.success:
            logger.debug("Mover item falló: %s", result.error_message or "Error desconocido")

    @staticmethod
    def _parse_payload(data: bytes) -> tuple[int | None, int | None]:
        """Extrae old_slot y new_slot del packet sin prevalidación.

        Args:
            data: Datos del packet.

        Returns:
            Tupla (old_slot, new_slot) o (None, None) si el packet es inválido.
        """
        if len(data) < MIN_PACKET_LENGTH:
            logger.warning("Packet MOVE_ITEM demasiado corto: len=%d", len(data))
            return None, None

        old_slot = data[1]
        new_slot = data[2]

        return old_slot, new_slot
