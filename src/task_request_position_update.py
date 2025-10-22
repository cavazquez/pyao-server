"""Tarea para procesar la solicitud de actualización de posición del cliente."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskRequestPositionUpdate(Task):
    """Tarea que maneja la solicitud de actualización de posición del cliente."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea RequestPositionUpdate.

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
        """Procesa la solicitud de actualización de posición."""
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Solicitud de posición sin estar logueado desde %s",
                self.message_sender.connection.address,
            )
            return

        if self.player_repo is None:
            logger.error("PlayerRepository no disponible para RequestPositionUpdate")
            return

        # Obtener posición actual del jugador desde Redis
        position = await self.player_repo.get_position(user_id)

        if position is None:
            logger.warning("No se encontró posición para user_id %d", user_id)
            # Enviar posición por defecto
            await self.message_sender.send_pos_update(50, 50)
            return

        # Enviar actualización de posición al cliente
        await self.message_sender.send_pos_update(position["x"], position["y"])
        logger.debug(
            "Posición enviada a user_id %d: (%d, %d)",
            user_id,
            position["x"],
            position["y"],
        )
