"""Tarea para retirar oro del banco."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.repositories.bank_repository import BankRepository
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskBankExtractGold(Task):
    """Maneja el retiro de oro del banco."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        amount: int,
        bank_repo: BankRepository | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de retiro de oro bancario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            amount: Cantidad de oro a retirar (ya validada).
            bank_repo: Repositorio de banco.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.amount = amount
        self.bank_repo = bank_repo
        self.player_repo = player_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el retiro de oro del banco.

        El amount ya fue validado por TaskFactory.
        """
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de retiro de oro bancario sin estar logueado")
            return

        if not self.bank_repo or not self.player_repo:
            logger.error("Dependencias no disponibles para retiro de oro bancario")
            await self.message_sender.send_console_msg("Error al retirar oro del banco")
            return

        logger.info(
            "user_id %d intenta retirar %d oro del banco",
            user_id,
            self.amount,
        )

        # Validar que la cantidad sea mayor a 0
        if self.amount <= 0:
            await self.message_sender.send_console_msg(
                "Debes especificar una cantidad mayor a 0 para retirar del banco."
            )
            return

        # Verificar que el banco tenga suficiente oro
        bank_gold = await self.bank_repo.get_gold(user_id)
        if bank_gold < self.amount:
            await self.message_sender.send_console_msg(
                f"No tienes suficiente oro en el banco. Tienes: {bank_gold}"
            )
            return

        # Retirar oro del banco
        success = await self.bank_repo.remove_gold(user_id, self.amount)
        if not success:
            await self.message_sender.send_console_msg("Error al retirar oro del banco")
            return

        # Agregar oro al jugador
        await self.player_repo.add_gold(user_id, self.amount)

        # Actualizar oro del jugador en cliente
        player_gold = await self.player_repo.get_gold(user_id)
        await self.message_sender.send_update_gold(player_gold)

        # Actualizar oro del banco en cliente
        bank_gold = await self.bank_repo.get_gold(user_id)
        await self.message_sender.send_update_bank_gold(bank_gold)

        # Mensaje de éxito
        await self.message_sender.send_console_msg(
            f"Retiraste {self.amount} oro del banco. Oro actual: {player_gold}"
        )

        logger.info(
            "user_id %d retiró %d oro del banco exitosamente",
            user_id,
            self.amount,
        )
