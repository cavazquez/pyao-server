"""Handler para comando de depositar item en el banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_deposit_command import BankDepositCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.models.items_catalog import ITEMS_CATALOG

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class BankDepositCommandHandler(CommandHandler):
    """Handler para comando de depositar item en el banco (solo lógica de negocio)."""

    def __init__(
        self,
        bank_repo: BankRepository,
        inventory_repo: InventoryRepository,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            bank_repo: Repositorio de banco.
            inventory_repo: Repositorio de inventario.
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes.
        """
        self.bank_repo = bank_repo
        self.inventory_repo = inventory_repo
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de depositar item en el banco (solo lógica de negocio).

        Args:
            command: Comando de depositar item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, BankDepositCommand):
            return CommandResult.error("Comando inválido: se esperaba BankDepositCommand")

        user_id = command.user_id
        slot = command.slot
        quantity = command.quantity

        logger.info(
            "BankDepositCommandHandler: user_id=%d depositando %d items del slot %d",
            user_id,
            quantity,
            slot,
        )

        try:
            # Obtener item del inventario
            inv_slot_data = await self.inventory_repo.get_slot(user_id, slot)
            if not inv_slot_data:
                await self.message_sender.send_console_msg("No tienes ningún item en ese slot")
                return CommandResult.error("No tienes ningún item en ese slot")

            item_id, amount = inv_slot_data
            if amount < quantity:
                await self.message_sender.send_console_msg(
                    f"Solo tienes {amount} items en ese slot"
                )
                return CommandResult.error(f"Solo tienes {amount} items en ese slot")

            # Depositar en el banco
            bank_slot = await self.bank_repo.deposit_item(user_id, item_id, quantity)

            if bank_slot is None:
                await self.message_sender.send_console_msg("No tienes espacio en el banco")
                return CommandResult.error("No tienes espacio en el banco")

            # Remover del inventario
            removed = await self.inventory_repo.remove_item(user_id, slot, quantity)

            # Verificar que la remoción fue exitosa
            if not removed:
                # Rollback: devolver items al banco
                await self.bank_repo.extract_item(user_id, bank_slot, quantity)
                await self.message_sender.send_console_msg("Error al depositar")
                logger.error(
                    "Fallo al remover items del inventario después de depositar. "
                    "Rollback ejecutado."
                )
                return CommandResult.error("Error al depositar")

            # Obtener datos del item para enviar al cliente
            item = ITEMS_CATALOG.get(item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", item_id)
                return CommandResult.error(f"Item {item_id} no encontrado en catálogo")

            # Actualizar slot del inventario en el cliente
            remaining = amount - quantity
            if remaining > 0:
                await self.message_sender.send_change_inventory_slot(
                    slot=slot,
                    item_id=item_id,
                    name=item.name,
                    amount=remaining,
                    equipped=False,
                    grh_id=item.graphic_id,
                    item_type=item.item_type.to_client_type(),
                    max_hit=item.max_damage or 0,
                    min_hit=item.min_damage or 0,
                    max_def=item.defense or 0,
                    min_def=item.defense or 0,
                    sale_price=float(item.value),
                )
            else:
                # Slot vacío
                await self.message_sender.send_change_inventory_slot(
                    slot=slot,
                    item_id=0,
                    name="",
                    amount=0,
                    equipped=False,
                    grh_id=0,
                    item_type=0,
                    max_hit=0,
                    min_hit=0,
                    max_def=0,
                    min_def=0,
                    sale_price=0.0,
                )

            # Actualizar slot del banco en el cliente
            bank_item = await self.bank_repo.get_item(user_id, bank_slot)
            if bank_item:
                await self.message_sender.send_change_bank_slot(
                    slot=bank_slot,
                    item_id=bank_item.item_id,
                    name=item.name,
                    amount=bank_item.quantity,
                    grh_id=item.graphic_id,
                    item_type=item.item_type.to_client_type(),
                    max_hit=item.max_damage or 0,
                    min_hit=item.min_damage or 0,
                    max_def=item.defense or 0,
                    min_def=item.defense or 0,
                )

            await self.message_sender.send_console_msg(
                f"Depositaste {quantity}x {item.name} en el banco"
            )

            logger.info(
                "user_id %d depositó %d x item_id %d en el banco (slot %d)",
                user_id,
                quantity,
                item_id,
                bank_slot,
            )

            return CommandResult.ok(
                data={"item_id": item_id, "quantity": quantity, "bank_slot": bank_slot}
            )

        except Exception as e:
            logger.exception("Error al depositar item en el banco")
            return CommandResult.error(f"Error al depositar: {e!s}")
