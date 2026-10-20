"""Recupera muertes pendientes al reconectar o tras una caída sin bloquear el tick."""

from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect
from src.services.combat.periodic import tick_periodic
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.player.player_death_service import PlayerDeathService


class LifecycleEffect(TickEffect):
    """Agenda liquidaciones propias; el recibo vital evita pérdidas repetidas."""

    def __init__(self, death_service: PlayerDeathService) -> None:
        """Recibe el servicio único del servidor."""
        self.death_service = death_service

    def get_name(self) -> str:
        """Identifica el efecto.

        Returns:
            Nombre estable del recuperador de muertes.
        """
        return "Lifecycle"

    def get_interval_seconds(self) -> float:
        """Devuelve la frecuencia de recuperación.

        Returns:
            Un segundo entre comprobaciones.
        """
        return 1.0

    async def apply(
        self, user_id: int, player_repo: PlayerRepository, message_sender: MessageSender | None
    ) -> None:
        """Recupera la liquidación de un muerto pendiente sin esperar sus barreras AOF."""
        if message_sender is None:
            return
        result = await tick_periodic(player_repo.redis.redis, user_id)
        if result.get("applied"):
            await message_sender.send_update_user_stats_from_repo(user_id, player_repo)
        await message_sender.sync_status(user_id, player_repo)
        await message_sender.status_effects.sync_campfires(user_id, player_repo)
        await message_sender.status_effects.sync_visibility(
            user_id, player_repo, self.death_service.map_manager
        )
        stats = await player_repo.redis.hgetall(RedisKeys.player_user_stats(user_id))
        if (
            stats
            and int(stats.get("min_hp", stats.get("hp", 0))) <= 0
            and stats.get("death_state") != "complete"
        ):
            self.death_service.schedule_death(
                user_id,
                "causas anteriores",
                "recuperación",
                expected_life_id=int(stats.get("life_id", 0)),
            )
