"""Tarea para manejar solicitudes de habilidades del jugador."""

import logging
from typing import TYPE_CHECKING

from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskRequestSkills(Task):
    """Maneja la solicitud de habilidades del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de solicitud de habilidades.

        Args:
            data: Datos del packet (vacío para REQUEST_SKILLS).
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data

    async def execute(self) -> None:
        """Ejecuta el envío de habilidades del jugador."""
        if not self.player_repo or not self.session_data:
            logger.warning("Datos de sesión o repositorio no disponibles para REQUEST_SKILLS")
            return

        user_id = self.session_data.get("user_id")
        if not user_id:
            logger.warning("Intento de solicitar habilidades sin estar logueado")
            return

        # Convertir a int si viene como dict
        if isinstance(user_id, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id)

        # Obtener habilidades del jugador
        skills = await self.player_repo.get_skills(user_id)
        if not skills:
            logger.warning("No se encontraron habilidades para user_id %d", user_id)
            # Enviar habilidades vacías o por defecto
            skills = {
                "magia": 0,
                "robustez": 0,
                "agilidad": 0,
                "talar": 0,
                "pesca": 0,
                "mineria": 0,
                "herreria": 0,
                "carpinteria": 0,
                "supervivencia": 0,
            }

        # Enviar habilidades al cliente
        await self.message_sender.send_update_skills(
            magic=skills.get("magia", 0),
            robustness=skills.get("robustez", 0),
            agility=skills.get("agilidad", 0),
            woodcutting=skills.get("talar", 0),
            fishing=skills.get("pesca", 0),
            mining=skills.get("mineria", 0),
            blacksmithing=skills.get("herreria", 0),
            carpentry=skills.get("carpinteria", 0),
            survival=skills.get("supervivencia", 0),
        )

        logger.info("Habilidades enviadas para user_id %d", user_id)
