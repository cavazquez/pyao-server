"""Efecto de meditación para recuperar mana automáticamente."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.effect import Effect  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Cantidad de mana recuperada por tick
MANA_RECOVERY_PER_TICK = 10


class MeditationEffect(Effect):  # type: ignore[misc]
    """Efecto que recupera mana para jugadores que están meditando."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        interval_seconds: float = 3.0,
    ) -> None:
        """Inicializa el efecto de meditación.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            interval_seconds: Intervalo en segundos entre recuperaciones (default: 3s).
        """
        super().__init__(interval_seconds)
        self.player_repo = player_repo
        self.map_manager = map_manager

    async def apply(self, message_sender: MessageSender, user_id: int) -> None:
        """Aplica recuperación de mana si el jugador está meditando.

        Args:
            message_sender: Enviador de mensajes.
            user_id: ID del usuario.
        """
        try:
            # Verificar si está meditando
            is_meditating = await self.player_repo.is_meditating(user_id)
            if not is_meditating:
                return

            # Obtener stats del jugador
            stats = await self.player_repo.get_stats(user_id)
            if not stats:
                return

            # Verificar que no tenga mana completo
            if stats["min_mana"] >= stats["max_mana"]:
                # Mana completo, detener meditación automáticamente
                await self.player_repo.set_meditating(user_id, is_meditating=False)
                await message_sender.send_meditate_toggle()
                await message_sender.send_console_msg("Tu mana está completo. Dejas de meditar.")
                logger.info("user_id %d dejó de meditar automáticamente (mana completo)", user_id)
                return

            # Recuperar mana
            old_mana = stats["min_mana"]
            stats["min_mana"] = min(stats["min_mana"] + MANA_RECOVERY_PER_TICK, stats["max_mana"])
            mana_recovered = stats["min_mana"] - old_mana

            # Actualizar stats en Redis
            await self.player_repo.set_stats(user_id=user_id, **stats)

            # Enviar actualización de stats al cliente
            await message_sender.send_update_user_stats(**stats)

            logger.debug(
                "user_id %d recuperó %d mana meditando (%d/%d)",
                user_id,
                mana_recovered,
                stats["min_mana"],
                stats["max_mana"],
            )

        except Exception:
            logger.exception("Error al aplicar efecto de meditación para user_id %d", user_id)
