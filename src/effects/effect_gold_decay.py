"""Efecto de reducción de oro."""

import logging
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class GoldDecayEffect(TickEffect):
    """Efecto de reducción de oro.

    Las constantes se leen desde Redis y pueden ser modificadas sin reiniciar el servidor.
    """

    def __init__(self, server_repo: ServerRepository) -> None:
        """Inicializa el efecto de reducción de oro.

        Args:
            server_repo: Repositorio del servidor para leer configuración.
        """
        self.server_repo = server_repo
        # Contadores por jugador: {user_id: ticks_elapsed}
        self._counters: dict[int, int] = {}

    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica la reducción de oro."""
        # Leer configuración desde Redis
        percentage = await self.server_repo.get_effect_config_float(
            RedisKeys.CONFIG_GOLD_DECAY_PERCENTAGE, 1.0
        )
        interval_seconds = await self.server_repo.get_effect_config_float(
            RedisKeys.CONFIG_GOLD_DECAY_INTERVAL, 60.0
        )

        # Inicializar contador si no existe
        if user_id not in self._counters:
            self._counters[user_id] = 0

        # Incrementar contador
        self._counters[user_id] += 1

        # Verificar si se cumplió el intervalo
        ticks_needed = int(interval_seconds / 1.0)  # Asumiendo tick de 1 segundo
        if self._counters[user_id] >= ticks_needed:
            self._counters[user_id] = 0

            # Obtener estadísticas actuales
            stats = await player_repo.get_stats(user_id)
            if not stats:
                logger.warning("No se encontraron stats para user_id %d", user_id)
                return

            current_gold = stats["gold"]
            if current_gold <= 0:
                return  # No hay oro para reducir

            # Calcular reducción
            reduction = max(1, int(current_gold * (percentage / 100.0)))
            new_gold = max(0, current_gold - reduction)

            # Actualizar estadísticas
            stats["gold"] = new_gold
            await player_repo.set_stats(user_id=user_id, **stats)

            logger.info(
                "user_id %d: oro reducido de %d a %d (-%d, %.1f%%)",
                user_id,
                current_gold,
                new_gold,
                reduction,
                percentage,
            )

            # Notificar al cliente
            if message_sender:
                await message_sender.send_update_user_stats(**stats)
                await message_sender.send_console_msg(
                    f"Has perdido {reduction} monedas de oro ({percentage}%)"
                )

    def get_interval_seconds(self) -> float:  # noqa: PLR6301
        """Retorna 1 segundo (se ejecuta cada segundo para contar intervalos).

        Returns:
            Intervalo en segundos.
        """
        return 1.0

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "GoldDecay"

    def cleanup_player(self, user_id: int) -> None:
        """Limpia los contadores de un jugador desconectado."""
        if user_id in self._counters:
            del self._counters[user_id]
