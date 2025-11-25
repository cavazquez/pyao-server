"""Handler para comando de depositar oro en el banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_deposit_gold_command import BankDepositGoldCommand
from src.commands.base import Command, CommandHandler, CommandResult

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class BankDepositGoldCommandHandler(CommandHandler):
    """Handler para comando de depositar oro en el banco (solo lógica de negocio)."""

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
        """Ejecuta el comando de depositar oro en el banco (solo lógica de negocio).

        Args:
            command: Comando de depositar oro.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, BankDepositGoldCommand):
            return CommandResult.error("Comando inválido: se esperaba BankDepositGoldCommand")

        user_id = command.user_id
        amount = command.amount

        logger.info(
            "BankDepositGoldCommandHandler: user_id=%d intenta depositar %d oro en el banco",
            user_id,
            amount,
        )

        try:
            # Validar que la cantidad sea mayor a 0
            if amount <= 0:
                await self.message_sender.send_console_msg(
                    "Debes especificar una cantidad mayor a 0 para depositar en el banco."
                )
                return CommandResult.error("Cantidad inválida: debe ser mayor a 0")

            # Verificar que el jugador tenga suficiente oro
            player_gold = await self.player_repo.get_gold(user_id)
            if player_gold < amount:
                await self.message_sender.send_console_msg(
                    f"No tienes suficiente oro. Tienes: {player_gold}"
                )
                return CommandResult.error(f"No tienes suficiente oro. Tienes: {player_gold}")

            # Remover oro del jugador
            success = await self.player_repo.remove_gold(user_id, amount)
            if not success:
                await self.message_sender.send_console_msg("Error al depositar oro en el banco")
                return CommandResult.error("Error al depositar oro en el banco")

            # Agregar oro al banco
            bank_gold = await self.bank_repo.add_gold(user_id, amount)

            # Actualizar oro del jugador en cliente
            player_gold = await self.player_repo.get_gold(user_id)
            await self.message_sender.send_update_gold(player_gold)

            # Actualizar oro del banco en cliente
            await self.message_sender.send_update_bank_gold(bank_gold)

            # Mensaje de éxito
            await self.message_sender.send_console_msg(
                f"Depositaste {amount} oro en el banco. Oro en banco: {bank_gold}"
            )

            logger.info(
                "user_id %d depositó %d oro en el banco exitosamente",
                user_id,
                amount,
            )

            return CommandResult.ok(data={"amount": amount, "bank_gold": bank_gold})

        except Exception as e:
            logger.exception("Error al depositar oro en el banco")
            return CommandResult.error(f"Error al depositar: {e!s}")
