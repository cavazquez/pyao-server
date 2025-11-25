"""Tarea para solicitud de atributos del personaje."""

import logging
from typing import TYPE_CHECKING

from src.commands.request_attributes_command import RequestAttributesCommand
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.request_attributes_handler import RequestAttributesCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskRequestAttributes(Task):
    """Tarea que maneja la solicitud de atributos del personaje.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        request_attributes_handler: RequestAttributesCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de solicitud de atributos.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            request_attributes_handler: Handler para el comando de solicitud de atributos.
            session_data: Datos de sesión compartidos (para obtener user_id o dice_attributes).
        """
        super().__init__(data, message_sender)
        self.request_attributes_handler = request_attributes_handler
        self.session_data = session_data

    async def execute(self) -> None:
        """Obtiene atributos y los envía al cliente (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.request_attributes_handler:
            logger.error("RequestAttributesCommandHandler no disponible")
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        # Primero verificar si hay atributos en sesión (creación de personaje)
        dice_attributes = None
        user_id = None

        if self.session_data and "dice_attributes" in self.session_data:
            dice_attributes = self.session_data["dice_attributes"]
            logger.info(
                "Atributos desde sesión encontrados para %s",
                self.message_sender.connection.address,
            )
        else:
            # Si no hay en sesión, obtener user_id para buscar en repositorio
            user_id = SessionManager.get_user_id(self.session_data)
            if user_id is None:
                logger.warning(
                    "Cliente %s solicitó atributos pero no hay user_id en sesión",
                    self.message_sender.connection.address,
                )
                await self.message_sender.send_attributes(0, 0, 0, 0, 0)
                return

            # Convertir user_id a int
            if isinstance(user_id, dict):
                logger.error("user_id en sesión es un dict, esperaba int")
                await self.message_sender.send_attributes(0, 0, 0, 0, 0)
                return

            user_id = int(user_id)

        # Crear comando (solo datos)
        command = RequestAttributesCommand(user_id=user_id, dice_attributes=dice_attributes)

        # Delegar al handler (separación de responsabilidades)
        result = await self.request_attributes_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Solicitud de atributos falló: %s", result.error_message or "Error desconocido"
            )
