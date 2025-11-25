"""Tarea que maneja el trabajo de los jugadores (talar, minar, pescar)."""

import logging
from typing import TYPE_CHECKING

from src.commands.work_command import WorkCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.work_handler import WorkCommandHandler
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes de direcciones (headings)
HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4


class TaskWork(Task):
    """Tarea que maneja el trabajo de los jugadores (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        work_handler: WorkCommandHandler | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de trabajo.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes.
            work_handler: Handler para el comando de trabajo.
            player_repo: Repositorio de jugadores (necesario para obtener posición).
            session_data: Datos de sesión compartidos.
        """
        super().__init__(data, message_sender)
        self.work_handler = work_handler
        self.player_repo = player_repo
        self.session_data = session_data

    async def execute(self) -> None:
        """Ejecuta la lógica de trabajo (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar dependencias básicas
        if not self.player_repo:
            logger.error("player_repo no disponible para trabajar")
            await self.message_sender.console.send_error_msg("Servicio de trabajo no disponible")
            return

        if not self.session_data or "user_id" not in self.session_data:
            logger.warning("No hay sesión activa para trabajar")
            await self.message_sender.console.send_error_msg("Debes iniciar sesión primero")
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Obtener posición y dirección del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return

        x = position["x"]
        y = position["y"]
        map_id = position["map"]
        heading = position["heading"]

        # Calcular posición objetivo (enfrente del jugador)
        target_x, target_y = TaskWork._get_target_position(x, y, heading)

        logger.info(
            "Usuario %d intenta trabajar en (%d, %d) mirando dirección %d -> objetivo (%d, %d)",
            user_id,
            x,
            y,
            heading,
            target_x,
            target_y,
        )

        # Validar que tenemos el handler
        if not self.work_handler:
            logger.error("WorkCommandHandler no disponible")
            await self.message_sender.console.send_error_msg("Servicio de trabajo no disponible")
            return

        # Crear comando (solo datos)
        command = WorkCommand(user_id=user_id, map_id=map_id, target_x=target_x, target_y=target_y)

        # Delegar al handler (separación de responsabilidades)
        result = await self.work_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Trabajar falló: %s", result.error_message or "Error desconocido")

    @staticmethod
    def _get_target_position(x: int, y: int, heading: int) -> tuple[int, int]:
        """Calcula la posición objetivo basándose en la dirección del jugador.

        Args:
            x: Posición X del jugador.
            y: Posición Y del jugador.
            heading: Dirección del jugador (1=Norte, 2=Este, 3=Sur, 4=Oeste).

        Returns:
            Tupla (target_x, target_y) de la posición objetivo.
        """
        if heading == HEADING_NORTH:
            return (x, y - 1)
        if heading == HEADING_EAST:
            return (x + 1, y)
        if heading == HEADING_SOUTH:
            return (x, y + 1)
        if heading == HEADING_WEST:
            return (x - 1, y)
        return (x, y)  # Fallback
