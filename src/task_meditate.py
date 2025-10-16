"""Tarea para meditar y recuperar mana."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Cantidad de mana recuperada por meditación
MANA_RECOVERY_PER_MEDITATION = 10


class TaskMeditate(Task):
    """Maneja la meditación para recuperar mana."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de meditar.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta la meditación."""
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de meditar sin estar logueado")
            return

        if not self.player_repo:
            logger.error("player_repo no disponible")
            return

        try:
            # Obtener stats del jugador
            stats = await self.player_repo.get_stats(user_id)
            if not stats:
                logger.warning("No se pudieron obtener stats del jugador %d", user_id)
                return

            # Verificar que no tenga mana completo
            if stats["min_mana"] >= stats["max_mana"]:
                await self.message_sender.send_console_msg("Ya tienes el mana completo.")
                return

            # Recuperar mana
            old_mana = stats["min_mana"]
            stats["min_mana"] = min(
                stats["min_mana"] + MANA_RECOVERY_PER_MEDITATION, stats["max_mana"]
            )
            mana_recovered = stats["min_mana"] - old_mana

            # Actualizar stats
            await self.player_repo.set_stats(user_id=user_id, **stats)

            # Enviar actualización de stats
            await self.message_sender.send_update_user_stats(**stats)

            # Enviar toggle de meditación (efecto visual)
            await self.message_sender.send_meditate_toggle()

            # Mensaje al jugador
            await self.message_sender.send_console_msg(
                f"Meditas y recuperas {mana_recovered} de mana."
            )

            logger.info(
                "user_id %d meditó y recuperó %d mana (%d/%d)",
                user_id,
                mana_recovered,
                stats["min_mana"],
                stats["max_mana"],
            )

        except Exception:
            logger.exception("Error al procesar meditación")
