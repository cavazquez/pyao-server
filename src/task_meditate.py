"""Tarea para meditar y recuperar mana."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


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
        """Ejecuta el toggle de meditación."""
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de meditar sin estar logueado")
            return

        if not self.player_repo:
            logger.error("player_repo no disponible")
            return

        try:
            # Obtener estado actual de meditación
            is_currently_meditating = await self.player_repo.is_meditating(user_id)

            # Toggle: cambiar estado
            new_state = not is_currently_meditating
            await self.player_repo.set_meditating(user_id, new_state)

            # Enviar toggle de meditación al cliente
            await self.message_sender.send_meditate_toggle()

            # Mensaje al jugador y efectos visuales
            if new_state:
                await self.message_sender.send_console_msg(
                    "Comienzas a meditar. Recuperaras mana automaticamente."
                )
                # Enviar FX de meditación con loop infinito (loops=-1)
                # FX 16 es el efecto de meditación en Argentum Online
                # Para jugadores, char_index = user_id (NPCs usan char_index >= 10001)
                await self.message_sender.send_create_fx(
                    char_index=user_id,
                    fx=16,
                    loops=-1,  # loops=-1 = infinito
                )
                logger.info("user_id %d comenzó a meditar", user_id)
            else:
                await self.message_sender.send_console_msg("Dejas de meditar.")
                # Cancelar FX de meditación enviando el mismo FX con loops=0
                # Esto detiene el efecto visual inmediatamente
                await self.message_sender.send_create_fx(
                    char_index=user_id,
                    fx=16,
                    loops=0,  # loops=0 = cancela el FX
                )
                logger.info("user_id %d dejó de meditar", user_id)

        except Exception:
            logger.exception("Error al procesar toggle de meditación")
