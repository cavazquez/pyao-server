"""Tarea para desconexión de usuarios."""

import logging
from typing import TYPE_CHECKING

from src.commands.quit_command import QuitCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.quit_handler import QuitCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskQuit(Task):
    """Tarea que maneja la desconexión ordenada del jugador.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        quit_handler: QuitCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Quit.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            quit_handler: Handler para el comando de desconexión.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.quit_handler = quit_handler
        self.session_data = session_data

    async def execute(self) -> None:
        """Procesa la desconexión ordenada del jugador (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.info(
                "Solicitud de desconexión sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        # Convertir user_id a int
        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        # Obtener username
        username = "Desconocido"
        if self.session_data and "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        # Validar que tenemos el handler
        if not self.quit_handler:
            logger.error("QuitCommandHandler no disponible")
            return

        # Crear comando (solo datos)
        command = QuitCommand(user_id=user_id_int, username=username)

        # Delegar al handler (separación de responsabilidades)
        result = await self.quit_handler.handle(command)

        # Limpiar sesión después de la desconexión
        if self.session_data:
            self.session_data.clear()
            logger.debug("Sesión limpiada para user_id %d", user_id_int)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Desconexión falló: %s", result.error_message or "Error desconocido")
