"""Efecto de meditación para recuperar mana automáticamente."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect
from src.services.meditation import meditate_tick
from src.services.player_progression import publish_progress

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository


class MeditationEffect(TickEffect):
    """Efecto que recupera mana para jugadores que están meditando."""

    def __init__(
        self,
        interval_seconds: float = 3.0,
    ) -> None:
        """Inicializa el efecto de meditación.

        Args:
            interval_seconds: Intervalo en segundos entre recuperaciones (default: 3s).
        """
        self.interval_seconds = interval_seconds

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:
        """Retorna el nombre del efecto para logging.

        Returns:
            Nombre del efecto.
        """
        return "Meditation"

    async def apply(
        self,
        user_id: int,
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica recuperación de mana si el jugador está meditando.

        Args:
            user_id: ID del usuario.
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes (puede ser None).
        """
        result = await meditate_tick(player_repo, user_id, self.interval_seconds)
        if not result.get("applied") or message_sender is None:
            return
        if result.get("stopped"):
            await message_sender.send_meditate_toggle()
            await message_sender.send_create_fx(char_index=user_id, fx=0, loops=0)
        if result.get("recovered"):
            await message_sender.send_update_mana(int(result["mana"]))
        await publish_progress(player_repo, user_id, message_sender)
