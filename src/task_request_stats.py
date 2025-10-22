"""Tarea para solicitar estadísticas del jugador."""

import logging
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskRequestStats(Task):
    """Tarea que maneja la solicitud de estadísticas del personaje."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea RequestStats.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la solicitud de estadísticas del jugador."""
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Solicitud de estadísticas recibida sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        # Convertir user_id a int
        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        logger.info("Solicitud de estadísticas de user_id %d", user_id_int)

        if not self.player_repo:
            await self.message_sender.send_console_msg("Error: Repositorio no disponible")
            return

        # Obtener estadísticas del jugador
        stats = await self.player_repo.get_stats(user_id_int)
        if not stats:
            await self.message_sender.send_console_msg(
                "Error: No se pudieron obtener las estadisticas"
            )
            return

        # Obtener atributos del jugador
        attributes = await self.player_repo.get_attributes(user_id_int)
        if not attributes:
            await self.message_sender.send_console_msg(
                "Error: No se pudieron obtener los atributos"
            )
            return

        # Obtener hambre y sed
        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id_int)
        if not hunger_thirst:
            await self.message_sender.send_console_msg("Error: No se pudieron obtener hambre y sed")
            return

        # Formatear mensaje de estadísticas
        stats_message = (
            f"--- Estadisticas ---\n"
            f"Nivel: {stats['level']}\n"
            f"Experiencia: {stats['experience']}/{stats['elu']}\n"
            f"Vida: {stats['min_hp']}/{stats['max_hp']}\n"
            f"Mana: {stats['min_mana']}/{stats['max_mana']}\n"
            f"Energia: {stats['min_sta']}/{stats['max_sta']}\n"
            f"Oro: {stats['gold']}\n"
            f"Hambre: {hunger_thirst['min_hunger']}/{hunger_thirst['max_hunger']}\n"
            f"Sed: {hunger_thirst['min_water']}/{hunger_thirst['max_water']}\n"
            f"--- Atributos ---\n"
            f"Fuerza: {attributes['strength']}\n"
            f"Agilidad: {attributes['agility']}\n"
            f"Inteligencia: {attributes['intelligence']}\n"
            f"Carisma: {attributes['charisma']}\n"
            f"Constitucion: {attributes['constitution']}"
        )

        # Enviar estadísticas línea por línea
        await self.message_sender.send_multiline_console_msg(stats_message)
        logger.info("Estadísticas enviadas para user_id %d", user_id_int)
