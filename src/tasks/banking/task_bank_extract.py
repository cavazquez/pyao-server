"""Tarea para extraer items del banco."""

import logging
from typing import TYPE_CHECKING

from src.models.items_catalog import ITEMS_CATALOG
from src.packet_data import BankExtractData
from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.repositories.bank_repository import BankRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskBankExtract(Task):
    """Maneja la extracción de items del banco."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        bank_repo: BankRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de extracción bancaria.

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
        """Ejecuta la extracción de un item del banco."""
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de extracción bancaria sin estar logueado")
            return

        if not self.bank_repo or not self.inventory_repo or not self.player_repo:
            logger.error("Dependencias no disponibles para extracción bancaria")
            await self.message_sender.send_console_msg("Error al extraer del banco")
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

        # Crear dataclass con datos validados
        extract_data = BankExtractData(slot=slot, quantity=quantity)

        logger.info(
            "user_id %d extrayendo %d items del slot %d del banco",
            user_id,
            extract_data.quantity,
            extract_data.slot,
        )

        try:
            # Obtener item del banco
            bank_item = await self.bank_repo.get_item(user_id, extract_data.slot)
            if not bank_item:
                await self.message_sender.send_console_msg(
                    "No hay ningún item en ese slot del banco"
                )
                return

            if bank_item.quantity < extract_data.quantity:
                await self.message_sender.send_console_msg(
                    f"Solo tienes {bank_item.quantity} items en ese slot del banco"
                )
                return

            # Extraer del banco
            success = await self.bank_repo.extract_item(
                user_id, extract_data.slot, extract_data.quantity
            )

            if not success:
                await self.message_sender.send_console_msg("Error al extraer del banco")
                return

            # Agregar al inventario
            modified_slots = await self.inventory_repo.add_item(
                user_id, bank_item.item_id, extract_data.quantity
            )

            if not modified_slots:
                logger.error("Error al agregar item al inventario después de extraer")
                # Revertir extracción
                await self.bank_repo.deposit_item(user_id, bank_item.item_id, extract_data.quantity)
                await self.message_sender.send_console_msg("No tienes espacio en el inventario")
                return

            # Obtener datos del item para enviar al cliente
            item = ITEMS_CATALOG.get(bank_item.item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", bank_item.item_id)
                return

            # PRIMERO: Actualizar slots del inventario en el cliente (igual que deposit)
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

        except Exception:
            logger.exception("Error al parsear packet BANK_EXTRACT_ITEM")
