"""Handler para comando de extraer item del banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_extract_command import BankExtractCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.models.items_catalog import ITEMS_CATALOG

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class BankExtractCommandHandler(CommandHandler):
    """Handler para comando de extraer item del banco (solo lógica de negocio)."""

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
        """Ejecuta el comando de extraer item del banco (solo lógica de negocio).

        Args:
            command: Comando de extraer item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, BankExtractCommand):
            return CommandResult.error("Comando inválido: se esperaba BankExtractCommand")

        user_id = command.user_id
        slot = command.slot
        quantity = command.quantity

        logger.info(
            "BankExtractCommandHandler: user_id=%d extrayendo %d items del slot %d del banco",
            user_id,
            quantity,
            slot,
        )

        try:
            # Obtener item del banco
            bank_item = await self.bank_repo.get_item(user_id, slot)
            if not bank_item:
                await self.message_sender.send_console_msg(
                    "No hay ningún item en ese slot del banco"
                )
                return CommandResult.error("No hay ningún item en ese slot del banco")

            if bank_item.quantity < quantity:
                await self.message_sender.send_console_msg(
                    f"Solo tienes {bank_item.quantity} items en ese slot del banco"
                )
                return CommandResult.error(
                    f"Solo tienes {bank_item.quantity} items en ese slot del banco"
                )

            # Extraer del banco
            success = await self.bank_repo.extract_item(user_id, slot, quantity)

            if not success:
                await self.message_sender.send_console_msg("Error al extraer del banco")
                return CommandResult.error("Error al extraer del banco")

            # Agregar al inventario
            modified_slots = await self.inventory_repo.add_item(
                user_id, bank_item.item_id, quantity
            )

            if not modified_slots:
                logger.error("Error al agregar item al inventario después de extraer")
                # Revertir extracción
                await self.bank_repo.deposit_item(user_id, bank_item.item_id, quantity)
                await self.message_sender.send_console_msg("No tienes espacio en el inventario")
                return CommandResult.error("No tienes espacio en el inventario")

            # Obtener datos del item para enviar al cliente
            item = ITEMS_CATALOG.get(bank_item.item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", bank_item.item_id)
                return CommandResult.error(f"Item {bank_item.item_id} no encontrado en catálogo")

            # PRIMERO: Actualizar slots del inventario en el cliente
            for inv_slot, inv_quantity in modified_slots:
                logger.info(
                    "Enviando ChangeInventorySlot: slot=%d, item_id=%d, cantidad=%d",
                    inv_slot,
                    bank_item.item_id,
                    inv_quantity,
                )
                await self.message_sender.send_change_inventory_slot(
                    slot=inv_slot,
                    item_id=bank_item.item_id,
                    name=item.name,
                    amount=inv_quantity,
                    equipped=False,
                    grh_id=item.graphic_id,
                    item_type=item.item_type.to_client_type(),
                    max_hit=item.max_damage or 0,
                    min_hit=item.min_damage or 0,
                    max_def=item.defense or 0,
                    min_def=item.defense or 0,
                    sale_price=float(item.value),
                )

            # DESPUÉS: Actualizar slot del banco en el cliente
            remaining_bank = bank_item.quantity - quantity
            if remaining_bank > 0:
                logger.info(
                    "Enviando ChangeBankSlot: slot=%d, item_id=%d, cantidad=%d",
                    slot,
                    bank_item.item_id,
                    remaining_bank,
                )
                await self.message_sender.send_change_bank_slot(
                    slot=slot,
                    item_id=bank_item.item_id,
                    name=item.name,
                    amount=remaining_bank,
                    grh_id=item.graphic_id,
                    item_type=item.item_type.to_client_type(),
                    max_hit=item.max_damage or 0,
                    min_hit=item.min_damage or 0,
                    max_def=item.defense or 0,
                    min_def=item.defense or 0,
                )
            else:
                # Slot vacío
                logger.info("Enviando ChangeBankSlot: slot=%d vaciado", slot)
                await self.message_sender.send_change_bank_slot(
                    slot=slot,
                    item_id=0,
                    name="",
                    amount=0,
                    grh_id=0,
                    item_type=0,
                    max_hit=0,
                    min_hit=0,
                    max_def=0,
                    min_def=0,
                )

            await self.message_sender.send_console_msg(
                f"Extrajiste {quantity}x {item.name} del banco"
            )

            logger.info(
                "user_id %d extrajo %d x item_id %d del banco (slot %d)",
                user_id,
                quantity,
                bank_item.item_id,
                slot,
            )

            return CommandResult.ok(
                data={
                    "item_id": bank_item.item_id,
                    "quantity": quantity,
                    "bank_slot": slot,
                    "inventory_slots": modified_slots,
                }
            )

        except Exception as e:
            logger.exception("Error al extraer item del banco")
            return CommandResult.error(f"Error al extraer: {e!s}")
