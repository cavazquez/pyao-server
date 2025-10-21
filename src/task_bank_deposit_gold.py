"""Tarea para depositar oro en el banco."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.bank_repository import BankRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskBankDepositGold(Task):
    """Maneja el depósito de oro en el banco."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        amount: int,
        bank_repo: BankRepository | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de depósito de oro bancario.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            amount: Cantidad de oro a depositar (ya validada).
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
        """Ejecuta el depósito de oro en el banco.

        El amount ya fue validado por TaskFactory.
        """
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de depósito de oro bancario sin estar logueado")
            return

        if not self.bank_repo or not self.player_repo:
            logger.error("Dependencias no disponibles para depósito de oro bancario")
            await self.message_sender.send_console_msg("Error al depositar oro en el banco")
            return

        logger.info(
            "user_id %d intenta depositar %d oro en el banco",
            user_id,
            self.amount,
        )

        # Validar que la cantidad sea mayor a 0
        if self.amount <= 0:
            await self.message_sender.send_console_msg(
                "Debes especificar una cantidad mayor a 0 para depositar en el banco."
            )
            return

        # Verificar que el jugador tenga suficiente oro
        player_gold = await self.player_repo.get_gold(user_id)
        if player_gold < self.amount:
            await self.message_sender.send_console_msg(
                f"No tienes suficiente oro. Tienes: {player_gold}"
            )
            return

        # Remover oro del jugador
        success = await self.player_repo.remove_gold(user_id, self.amount)
        if not success:
            await self.message_sender.send_console_msg("Error al depositar oro en el banco")
            return

        # Agregar oro al banco
        bank_gold = await self.bank_repo.add_gold(user_id, self.amount)

        # Actualizar oro del jugador en cliente
        player_gold = await self.player_repo.get_gold(user_id)
        await self.message_sender.send_update_gold(player_gold)

        # Actualizar oro del banco en cliente
        await self.message_sender.send_update_bank_gold(bank_gold)

        # Mensaje de éxito
        await self.message_sender.send_console_msg(
            f"Depositaste {self.amount} oro en el banco. Oro en banco: {bank_gold}"
        )

        logger.info(
            "user_id %d depositó %d oro en el banco exitosamente",
            user_id,
            self.amount,
        )
