"""Efecto periódico de envenenamiento para jugadores."""

import logging
import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes de envenenamiento
POISON_DAMAGE_PER_TICK = 5  # Daño por tick
POISON_TICK_INTERVAL = 2.0  # Segundos entre ticks de daño
POISON_DEFAULT_DURATION = 30.0  # Duración por defecto en segundos


class PoisonEffect(TickEffect):
    """Efecto que aplica daño periódico a jugadores envenenados."""

    def __init__(self, interval_seconds: float = POISON_TICK_INTERVAL) -> None:
        """Inicializa el efecto de envenenamiento.

        Args:
            interval_seconds: Intervalo en segundos entre aplicaciones del efecto.
        """
        self.interval_seconds = interval_seconds

    async def apply(  # noqa: PLR6301
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica el daño de envenenamiento si el jugador está envenenado.

        Args:
            user_id: ID del usuario.
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes (puede ser None).
        """
        current_time = time.time()

        # Obtener estado de envenenamiento
        poisoned_until = await player_repo.get_poisoned_until(user_id)

        # Si no está envenenado o el efecto expiró, no hacer nada
        if poisoned_until <= 0.0 or current_time >= poisoned_until:
            # Limpiar el estado si expiró
            if poisoned_until > 0.0 and current_time >= poisoned_until:
                await player_repo.update_poisoned_until(user_id, 0.0)
                logger.debug("Envenenamiento expirado para user_id %d", user_id)
            return

        # Verificar que el jugador esté vivo
        is_alive = await player_repo.is_alive(user_id)
        if not is_alive:
            # Limpiar envenenamiento si el jugador murió
            await player_repo.update_poisoned_until(user_id, 0.0)
            logger.debug("Envenenamiento limpiado para user_id %d (jugador muerto)", user_id)
            return

        # Obtener stats del jugador
        stats = await player_repo.get_player_stats(user_id)
        if not stats:
            logger.warning("No se pudieron obtener stats para user_id %d", user_id)
            return

        # Aplicar daño de envenenamiento
        new_hp = max(0, stats.min_hp - POISON_DAMAGE_PER_TICK)

        # Actualizar HP
        await player_repo.update_hp(user_id, new_hp)

        # Notificar al cliente si hay MessageSender
        if message_sender:
            await message_sender.send_update_user_stats(
                max_hp=stats.max_hp,
                min_hp=new_hp,
                max_mana=stats.max_mana,
                min_mana=stats.min_mana,
                max_sta=stats.max_sta,
                min_sta=stats.min_sta,
                gold=stats.gold,
                level=stats.level,
                elu=stats.elu,
                experience=stats.experience,
            )

        # Verificar si el jugador murió
        if new_hp <= 0:
            logger.info(
                "user_id %d murió por envenenamiento (HP: %d/%d)",
                user_id,
                new_hp,
                stats.max_hp,
            )
            # Limpiar envenenamiento al morir
            await player_repo.update_poisoned_until(user_id, 0.0)
        else:
            logger.debug(
                "user_id %d recibió daño de envenenamiento: %d -> %d HP (expira en %.1fs)",
                user_id,
                stats.min_hp,
                new_hp,
                poisoned_until - current_time,
            )

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "Poison"
