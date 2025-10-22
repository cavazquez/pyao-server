"""Servicio para gestionar consumo y regeneración de stamina/energía."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes de consumo de stamina
STAMINA_COST_WALK = 1  # Consumo por movimiento
STAMINA_COST_ATTACK = 2  # Consumo por ataque
STAMINA_COST_SPELL = 3  # Consumo por hechizo
STAMINA_COST_WORK = 5  # Consumo por trabajar (talar, minar, etc.)

# Constantes de regeneración
STAMINA_REGEN_RATE = 2  # Puntos de stamina regenerados por tick
STAMINA_REGEN_RESTING = 5  # Puntos regenerados si está descansando (sin moverse)


class StaminaService:
    """Servicio para gestionar stamina del jugador."""

    def __init__(self, player_repo: PlayerRepository) -> None:
        """Inicializa el servicio de stamina.

        Args:
            player_repo: Repositorio de jugadores.
        """
        self.player_repo = player_repo

    async def consume_stamina(
        self,
        user_id: int,
        amount: int,
        message_sender: MessageSender | None = None,
    ) -> bool:
        """Consume stamina del jugador.

        Args:
            user_id: ID del jugador.
            amount: Cantidad de stamina a consumir.
            message_sender: MessageSender para enviar update al cliente.

        Returns:
            True si se pudo consumir, False si no tiene suficiente stamina.
        """
        min_sta, _ = await self.player_repo.get_stamina(user_id)

        # Verificar si tiene suficiente stamina
        if min_sta < amount:
            if message_sender:
                await message_sender.send_console_msg("No tienes suficiente energía.")
            return False

        # Consumir stamina
        new_stamina = max(0, min_sta - amount)
        await self.player_repo.update_stamina(user_id, new_stamina)

        # Enviar update al cliente
        if message_sender:
            await message_sender.send_update_sta(new_stamina)

        logger.debug(
            "Stamina consumida: user_id=%d, amount=%d, new_stamina=%d",
            user_id,
            amount,
            new_stamina,
        )

        return True

    async def can_perform_action(self, user_id: int, stamina_cost: int) -> bool:
        """Verifica si el jugador tiene suficiente stamina para una acción.

        Args:
            user_id: ID del jugador.
            stamina_cost: Costo de stamina de la acción.

        Returns:
            True si tiene suficiente stamina, False en caso contrario.
        """
        min_sta, _ = await self.player_repo.get_stamina(user_id)
        return min_sta >= stamina_cost

    async def regenerate_stamina(
        self,
        user_id: int,
        amount: int,
        message_sender: MessageSender | None = None,
    ) -> None:
        """Regenera stamina del jugador.

        Args:
            user_id: ID del jugador.
            amount: Cantidad de stamina a regenerar.
            message_sender: MessageSender para enviar update al cliente.
        """
        min_sta, max_sta = await self.player_repo.get_stamina(user_id)

        # No regenerar si ya está al máximo
        if min_sta >= max_sta:
            return

        # Regenerar stamina (sin exceder el máximo)
        new_stamina = min(max_sta, min_sta + amount)
        await self.player_repo.update_stamina(user_id, new_stamina)

        # Enviar update al cliente
        if message_sender:
            await message_sender.send_update_sta(new_stamina)

        logger.debug(
            "Stamina regenerada: user_id=%d, amount=%d, new_stamina=%d",
            user_id,
            amount,
            new_stamina,
        )

    async def should_regenerate(self, user_id: int) -> bool:
        """Verifica si el jugador debería regenerar stamina.

        La stamina se regenera solo si el jugador tiene hambre > 0 y sed > 0.

        Args:
            user_id: ID del jugador.

        Returns:
            True si debería regenerar, False en caso contrario.
        """
        # Obtener hambre y sed
        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)
        if not hunger_thirst:
            return False

        min_hunger = hunger_thirst.get("min_hunger", 0)
        min_water = hunger_thirst.get("min_water", 0)

        # Solo regenerar si tiene hambre > 0 y sed > 0
        return min_hunger > 0 and min_water > 0
