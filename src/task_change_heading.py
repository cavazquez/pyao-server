"""Tarea para manejar el cambio de dirección del personaje."""

import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes para direcciones
HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4

# Constantes para validación de paquetes
MIN_CHANGE_HEADING_PACKET_SIZE = 2


class TaskChangeHeading(Task):
    """Tarea que maneja el cambio de dirección del personaje sin moverse."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de cambio de dirección.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data

    def _parse_packet(self) -> int | None:
        """Parsea el paquete de cambio de dirección.

        El formato esperado es:
        - Byte 0: PacketID (CHANGE_HEADING = 37)
        - Byte 1: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste)

        Returns:
            Dirección o None si hay error.
        """
        try:
            if len(self.data) < MIN_CHANGE_HEADING_PACKET_SIZE:
                return None

            heading = int(self.data[1])

            # Validar dirección (1-4)
            if heading < HEADING_NORTH or heading > HEADING_WEST:
                logger.warning("Dirección inválida: %d", heading)
                return None

        except (ValueError, IndexError) as e:
            logger.warning("Error parseando paquete de cambio de dirección: %s", e)
            return None
        else:
            return heading

    async def execute(self) -> None:
        """Ejecuta el cambio de dirección del personaje."""
        # Parsear dirección
        heading = self._parse_packet()
        if heading is None:
            logger.warning(
                "Paquete de cambio de dirección inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Verificar que el player_repo esté disponible
        if self.player_repo is None:
            logger.error("PlayerRepository no está disponible para cambio de dirección")
            return

        # Obtener user_id de la sesión
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de cambio de dirección sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Guardar la dirección en Redis
        await self.player_repo.set_heading(user_id, heading)

        logger.info(
            "User %d cambió dirección a %d",
            user_id,
            heading,
        )

        # Nota: El cliente ya cambió la dirección localmente.
        # En el futuro: Enviar CHARACTER_CHANGE a otros jugadores para que vean el cambio
