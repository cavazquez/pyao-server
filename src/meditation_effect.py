"""Efecto de meditación para recuperar mana automáticamente."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Cantidad de mana recuperada por tick
MANA_RECOVERY_PER_TICK = 10


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

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto para logging.

        Returns:
            Nombre del efecto.
        """
        return "Meditation"

    async def apply(  # noqa: PLR6301
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
        try:
            # Verificar si está meditando
            is_meditating = await player_repo.is_meditating(user_id)
            if not is_meditating:
                return

            # Obtener stats del jugador
            stats = await player_repo.get_stats(user_id)
            if not stats:
                return

            # Verificar que no tenga mana completo
            if stats["min_mana"] >= stats["max_mana"]:
                # Mana completo, detener meditación automáticamente
                await player_repo.set_meditating(user_id, is_meditating=False)
                if message_sender:
                    await message_sender.send_meditate_toggle()
                    await message_sender.send_console_msg(
                        "Tu mana esta completo. Dejas de meditar."
                    )
                logger.info("user_id %d dejó de meditar automáticamente (mana completo)", user_id)
                return

            # Recuperar mana
            old_mana = stats["min_mana"]
            stats["min_mana"] = min(stats["min_mana"] + MANA_RECOVERY_PER_TICK, stats["max_mana"])
            mana_recovered = stats["min_mana"] - old_mana

            # Actualizar stats en Redis
            await player_repo.set_stats(user_id=user_id, **stats)

            # Enviar actualización de stats al cliente
            if message_sender:
                # Enviar UPDATE_MANA específico
                await message_sender.send_update_mana(stats["min_mana"])
                # También enviar UPDATE_USER_STATS completo
                await message_sender.send_update_user_stats(**stats)

            logger.info(
                "user_id %d recuperó %d mana meditando (%d/%d)",
                user_id,
                mana_recovered,
                stats["min_mana"],
                stats["max_mana"],
            )

        except Exception:
            logger.exception("Error al aplicar efecto de meditación para user_id %d", user_id)
