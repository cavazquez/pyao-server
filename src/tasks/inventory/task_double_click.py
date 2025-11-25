"""Tarea para doble click (items del inventario o NPCs)."""

import logging
from typing import TYPE_CHECKING

from src.commands.double_click_command import DoubleClickCommand
from src.network.packet_data import DoubleClickData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task
from src.utils.packet_length_validator import PacketLengthValidator

if TYPE_CHECKING:
    from src.command_handlers.double_click_handler import DoubleClickCommandHandler
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskDoubleClick(Task):
    """Maneja doble click en items del inventario o NPCs.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        double_click_handler: DoubleClickCommandHandler | None = None,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de doble click.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            double_click_handler: Handler para el comando de doble click.
            player_repo: Repositorio de jugadores (necesario para obtener mapa).
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.double_click_handler = double_click_handler
        self.player_repo = player_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta doble click (item o NPC) (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar longitud del packet usando PacketLengthValidator
        if not await PacketLengthValidator.validate_min_length(self.data, 3, self.message_sender):
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de doble click sin estar logueado")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        target = validator.read_slot(min_slot=0, max_slot=255)  # Puede ser slot, CharIndex o mapa

        if validator.has_errors() or target is None:
            error_msg = (
                validator.get_error_message() if validator.has_errors() else "Target inválido"
            )
            await self.message_sender.send_console_msg(error_msg)
            return

        # Crear dataclass con datos validados
        click_data = DoubleClickData(target=target)

        # Doble click en el mapa envía coordenadas adicionales (x, y)
        if reader.has_more_data():
            remaining_coords: list[int] = []
            while reader.has_more_data():
                remaining_coords.append(reader.read_byte())

            logger.debug(
                "Doble click sobre el mapa detectado: coords=%s, se ignora.",
                [click_data.target, *remaining_coords],
            )
            return

        if click_data.target == 0:
            logger.debug("Doble click sobre el mapa (target=0), se ignora.")
            return

        # Obtener mapa del jugador (necesario para NPCs)
        map_id = None
        if self.player_repo:
            position = await self.player_repo.get_position(user_id)
            if position:
                map_id = position["map"]

        # Validar que tenemos el handler
        if not self.double_click_handler:
            logger.error("DoubleClickCommandHandler no disponible")
            await self.message_sender.send_console_msg("Servicio no disponible")
            return

        # Crear comando (solo datos)
        command = DoubleClickCommand(
            user_id=user_id,
            target=click_data.target,
            map_id=map_id,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.double_click_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Doble click falló: %s", result.error_message or "Error desconocido")
