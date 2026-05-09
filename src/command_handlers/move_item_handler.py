"""Handler para comando de mover items en el inventario."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.move_item_command import MoveItemCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository

logger = logging.getLogger(__name__)


class MoveItemCommandHandler(CommandHandler):
    """Handler para comando de mover items (solo lógica de negocio)."""

    def __init__(
        self,
        inventory_repo: InventoryRepository,
        item_catalog: ItemCatalog | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler con dependencias.

        Args:
            inventory_repo: Repositorio de inventario.
            item_catalog: Catálogo de items (opcional).
            message_sender: Enviador de mensajes.
        """
        self.inventory_repo = inventory_repo
        self.item_catalog = item_catalog
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de mover item en inventario.

        Args:
            command: Comando MoveItemCommand con old_slot y new_slot.

        Returns:
            Resultado de la operación.
        """
        if not isinstance(command, MoveItemCommand):
            return CommandResult.error("Comando inválido: se esperaba MoveItemCommand")

        user_id = command.user_id
        old_slot = command.old_slot
        new_slot = command.new_slot

        logger.info(
            "MoveItemCommandHandler: user_id=%d mueve item slot=%d -> slot=%d",
            user_id,
            old_slot,
            new_slot,
        )

        try:
            result = await self.inventory_repo.swap_slots(user_id, old_slot, new_slot)
        except Exception:
            logger.exception("Error inesperado moviendo item en inventario")
            return CommandResult.error("Error inesperado al mover item")

        if result is None:
            return CommandResult.error("Servicio no disponible")

        if not result.success:
            error_msg = result.reason or "No se pudo mover el item."
            await self.message_sender.send_console_msg(error_msg)
            return CommandResult.error(error_msg)

        # Enviar actualización de ambos slots al cliente
        await self._send_slot_update(user_id, result.old_slot, result.old_slot_data)
        await self._send_slot_update(user_id, result.new_slot, result.new_slot_data)

        return CommandResult.ok(
            data={
                "old_slot": result.old_slot,
                "new_slot": result.new_slot,
            }
        )

    async def _send_slot_update(
        self, _user_id: int, slot: int, slot_data: tuple[int, int] | None
    ) -> None:
        """Envía la actualización de un slot del inventario al cliente."""
        if slot_data is None:
            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=0,
                name="",
                amount=0,
                equipped=False,
                grh_id=0,
                item_type=0,
            )
            return

        item_id, quantity = slot_data

        if self.item_catalog is None:
            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=item_id,
                name=f"Item {item_id}",
                amount=quantity,
                equipped=False,
                grh_id=0,
                item_type=0,
            )
            return

        item_name = self.item_catalog.get_item_name(item_id) or f"Item {item_id}"
        grh_id = self.item_catalog.get_grh_index(item_id) or 0

        item_data = self.item_catalog.get_item_data(item_id)
        obj_type: int = 0
        if item_data and "obj_type" in item_data:
            val = item_data["obj_type"]
            if isinstance(val, int):
                obj_type = val

        await self.message_sender.send_change_inventory_slot(
            slot=slot,
            item_id=item_id,
            name=item_name,
            amount=quantity,
            equipped=False,
            grh_id=grh_id,
            item_type=obj_type,
        )
