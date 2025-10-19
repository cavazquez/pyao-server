"""Tarea para depositar items en el banco."""

import logging
from typing import TYPE_CHECKING

from src.items_catalog import ITEMS_CATALOG
from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.bank_repository import BankRepository
    from src.inventory_repository import InventoryRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskBankDeposit(Task):
    """Maneja el depósito de items en el banco."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        bank_repo: BankRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de depósito bancario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            bank_repo: Repositorio de banco.
            inventory_repo: Repositorio de inventario.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.bank_repo = bank_repo
        self.inventory_repo = inventory_repo
        self.player_repo = player_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el depósito de un item en el banco."""
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de depósito bancario sin estar logueado")
            return

        if not self.bank_repo or not self.inventory_repo or not self.player_repo:
            logger.error("Dependencias no disponibles para depósito bancario")
            await self.message_sender.send_console_msg("Error al depositar en el banco")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        slot = validator.read_slot(min_slot=1, max_slot=20)
        quantity = validator.read_quantity(min_qty=1, max_qty=10000)

        if validator.has_errors() or slot is None or quantity is None:
            error_msg = (
                validator.get_error_message() if validator.has_errors() else "Datos inválidos"
            )
            await self.message_sender.send_console_msg(error_msg)
            return

        logger.info("user_id %d depositando %d items del slot %d", user_id, quantity, slot)

        try:
            # Obtener item del inventario
            inv_slot_data = await self.inventory_repo.get_slot(user_id, slot)
            if not inv_slot_data:
                await self.message_sender.send_console_msg("No tienes ningún item en ese slot")
                return

            item_id, amount = inv_slot_data
            if amount < quantity:
                await self.message_sender.send_console_msg(
                    f"Solo tienes {amount} items en ese slot"
                )
                return

            # Depositar en el banco
            bank_slot = await self.bank_repo.deposit_item(user_id, item_id, quantity)

            if bank_slot is None:
                await self.message_sender.send_console_msg("No tienes espacio en el banco")
                return

            # Remover del inventario
            success = await self.inventory_repo.remove_item(user_id, slot, quantity)

            if not success:
                logger.error("Error al remover item del inventario después de depositar")
                await self.message_sender.send_console_msg("Error al depositar")
                return

            # Obtener datos del item para enviar al cliente
            item = ITEMS_CATALOG.get(item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", item_id)
                return

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

        except Exception:
            logger.exception("Error al parsear packet BANK_DEPOSIT")
