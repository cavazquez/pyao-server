"""Tarea para manejar trabajo con click (pesca, tala, minería)."""

import logging
from typing import TYPE_CHECKING

from src.commands.work_left_click_command import WorkLeftClickCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.work_left_click_handler import WorkLeftClickCommandHandler
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes de packet
MIN_PACKET_LENGTH = 4


class TaskWorkLeftClick(Task):
    """Maneja el trabajo con click (pesca, tala, minería) en coordenadas específicas.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        work_left_click_handler: WorkLeftClickCommandHandler | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de trabajo con click.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            work_left_click_handler: Handler para el comando de trabajo con click.
            player_repo: Repositorio de jugadores (necesario para obtener mapa).
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.work_left_click_handler = work_left_click_handler
        self.player_repo = player_repo
        self.session_data = session_data

    def _extract_work_data(self) -> tuple[int, int, int]:
        """Extrae coordenadas y skill_type del packet.

        Returns:
            Tupla (target_x, target_y, skill_type).

        Raises:
            IndexError: Si el packet no tiene la longitud mínima requerida.
        """
        if len(self.data) < MIN_PACKET_LENGTH:
            msg = "Packet demasiado corto para datos de trabajo"
            raise IndexError(msg)

        target_x = self.data[1]
        target_y = self.data[2]
        skill_type = self.data[3]
        return target_x, target_y, skill_type

    async def execute(self) -> None:
        """Ejecuta el trabajo en las coordenadas clickeadas (solo parsing y delegación).

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

        # Extraer coordenadas y skill_type del packet
        try:
            target_x, target_y, skill_type = self._extract_work_data()
        except IndexError:
            logger.warning("Packet WORK_LEFT_CLICK demasiado corto")
            return

        # Obtener mapa del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return

        map_id = position["map"]

        logger.info(
            "Usuario %d hace WORK_LEFT_CLICK en (%d, %d) con skill=%d",
            user_id,
            target_x,
            target_y,
            skill_type,
        )

        # Validar que tenemos el handler
        if not self.work_left_click_handler:
            logger.error("WorkLeftClickCommandHandler no disponible")
            await self.message_sender.console.send_error_msg("Servicio de trabajo no disponible")
            return

        # Crear comando (solo datos)
        command = WorkLeftClickCommand(
            user_id=user_id,
            map_id=map_id,
            target_x=target_x,
            target_y=target_y,
            skill_type=skill_type,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.work_left_click_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Trabajar con click falló: %s", result.error_message or "Error desconocido"
            )
