"""Tarea para click izquierdo en personajes/NPCs."""

import logging
from typing import TYPE_CHECKING

from src.commands.left_click_command import LeftClickCommand
from src.network.packet_data import LeftClickData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task
from src.utils.packet_length_validator import PacketLengthValidator

if TYPE_CHECKING:
    from src.command_handlers.left_click_handler import LeftClickCommandHandler
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskLeftClick(Task):
    """Maneja click izquierdo en personajes/NPCs.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        left_click_handler: LeftClickCommandHandler | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de click izquierdo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            left_click_handler: Handler para el comando de click izquierdo.
            player_repo: Repositorio de jugadores (necesario para obtener mapa).
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.left_click_handler = left_click_handler
        self.player_repo = player_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta click izquierdo en personaje/NPC (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar longitud del packet usando PacketLengthValidator
        if not await PacketLengthValidator.validate_min_length(self.data, 26, self.message_sender):
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de click sin estar logueado")
            return

        if not self.player_repo:
            logger.error("player_repo no disponible para click")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        # Usar nueva API consistente
        coords_result = validator.validate_coordinates(max_x=100, max_y=100)

        if not coords_result.success:
            await self.message_sender.send_console_msg(
                coords_result.error_message or "Coordenadas inválidas"
            )
            return

        # Crear dataclass con datos validados
        if coords_result.data is None:
            await self.message_sender.send_console_msg("Coordenadas inválidas")
            return
        x, y = coords_result.data
        click_data = LeftClickData(x=x, y=y)

        logger.info(
            "user_id %d hizo click en posición (%d, %d)", user_id, click_data.x, click_data.y
        )

        # Obtener posición del jugador para saber en qué mapa está
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return

        map_id = position["map"]

        # Validar que tenemos el handler
        if not self.left_click_handler:
            logger.error("LeftClickCommandHandler no disponible")
            await self.message_sender.send_console_msg("Servicio no disponible")
            return

        # Crear comando (solo datos)
        command = LeftClickCommand(
            user_id=user_id,
            map_id=map_id,
            x=click_data.x,
            y=click_data.y,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.left_click_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Click izquierdo falló: %s", result.error_message or "Error desconocido")
