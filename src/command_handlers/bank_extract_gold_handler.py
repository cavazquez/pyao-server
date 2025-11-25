"""Handler para comando de extraer oro del banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_extract_gold_command import BankExtractGoldCommand
from src.commands.base import Command, CommandHandler, CommandResult

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class BankExtractGoldCommandHandler(CommandHandler):
    """Handler para comando de extraer oro del banco (solo lógica de negocio)."""

    def __init__(
        self,
        bank_repo: BankRepository,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            bank_repo: Repositorio de banco.
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes.
        """
        self.bank_repo = bank_repo
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de extraer oro del banco (solo lógica de negocio).

        Args:
            command: Comando de extraer oro.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, BankExtractGoldCommand):
            return CommandResult.error("Comando inválido: se esperaba BankExtractGoldCommand")

        user_id = command.user_id
        amount = command.amount

        logger.info(
            "BankExtractGoldCommandHandler: user_id=%d intenta retirar %d oro del banco",
            user_id,
            amount,
        )

        try:
            # Validar que la cantidad sea mayor a 0
            if amount <= 0:
                await self.message_sender.send_console_msg(
                    "Debes especificar una cantidad mayor a 0 para retirar del banco."
                )
                return CommandResult.error("Cantidad inválida: debe ser mayor a 0")

            # Verificar que el banco tenga suficiente oro
            bank_gold = await self.bank_repo.get_gold(user_id)
            if bank_gold < amount:
                await self.message_sender.send_console_msg(
                    f"No tienes suficiente oro en el banco. Tienes: {bank_gold}"
                )
                return CommandResult.error(
                    f"No tienes suficiente oro en el banco. Tienes: {bank_gold}"
                )

            # Retirar oro del banco
            success = await self.bank_repo.remove_gold(user_id, amount)
            if not success:
                await self.message_sender.send_console_msg("Error al retirar oro del banco")
                return CommandResult.error("Error al retirar oro del banco")

            # Agregar oro al jugador
            await self.player_repo.add_gold(user_id, amount)

            # Actualizar oro del jugador en cliente
            player_gold = await self.player_repo.get_gold(user_id)
            await self.message_sender.send_update_gold(player_gold)

            # Actualizar oro del banco en cliente
            bank_gold = await self.bank_repo.get_gold(user_id)
            await self.message_sender.send_update_bank_gold(bank_gold)

            # Mensaje de éxito
            await self.message_sender.send_console_msg(
                f"Retiraste {amount} oro del banco. Oro actual: {player_gold}"
            )

            logger.info(
                "user_id %d retiró %d oro del banco exitosamente",
                user_id,
                amount,
            )

            return CommandResult.ok(data={"amount": amount, "player_gold": player_gold})

        except Exception as e:
            logger.exception("Error al retirar oro del banco")
            return CommandResult.error(f"Error al retirar: {e!s}")
