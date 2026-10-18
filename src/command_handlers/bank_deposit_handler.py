"""Transferencia atómica de objetos entre banco e inventario."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_deposit_command import BankDepositCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.config.config_manager import ConfigManager
from src.services.bank_item_transfer import transfer_bank_item
from src.services.inventory_notifications import notify_bank, notify_inventory

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class BankDepositCommandHandler(CommandHandler):
    """Confirma los dos contenedores antes de notificar al cliente."""

    def __init__(
        self,
        bank_repo: BankRepository,
        inventory_repo: InventoryRepository,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
    ) -> None:
        """Conserva los repositorios y el emisor de la sesión."""
        self.bank_repo = bank_repo
        self.inventory_repo = inventory_repo
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta una transferencia identificada con resultado confirmado.

        Returns:
            Resultado del commit o rechazo sin compensaciones separadas.
        """
        if not isinstance(command, BankDepositCommand):
            return CommandResult.error("Comando inválido")
        try:
            result = await transfer_bank_item(
                self.bank_repo.redis_client.redis,
                command.user_id,
                command.slot,
                command.quantity,
                "deposit",
                command.operation_id,
                inventory_slots=ConfigManager.as_int(self.inventory_repo.MAX_SLOTS),
                bank_slots=ConfigManager.as_int(self.bank_repo.MAX_SLOTS),
                inventory_stack=self.inventory_repo.stacking.max_stack,
            )
            if not result["applied"]:
                await self.message_sender.send_console_msg(result["error"])
                return CommandResult.error(result["error"])
            await notify_inventory(self.message_sender, self.inventory_repo, command.user_id)
            await notify_bank(self.message_sender, self.bank_repo, command.user_id)
            await self.message_sender.send_console_msg(
                f"Depositaste {command.quantity}x {result['name']}."
            )
            return CommandResult.ok(data=result)
        except ValueError as error:
            await self.message_sender.send_console_msg(str(error))
            return CommandResult.error(str(error))
        except Exception:
            logger.exception("No se pudo confirmar la transferencia bancaria")
            return CommandResult.error(
                "No se pudo confirmar la operación; revisá ambos inventarios."
            )
