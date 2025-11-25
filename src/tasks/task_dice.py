"""Tarea para tirada de dados."""

import logging
from typing import TYPE_CHECKING

from src.commands.dice_command import DiceCommand
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.dice_handler import DiceCommandHandler
    from src.messaging.message_sender import MessageSender
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class TaskDice(Task):
    """Tarea que maneja la tirada de dados.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        dice_handler: DiceCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        server_repo: ServerRepository | None = None,
    ) -> None:
        """Inicializa la tarea de tirada de dados.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            dice_handler: Handler para el comando de tirada de dados.
            session_data: Datos de sesión compartidos (opcional).
            server_repo: Repositorio del servidor para obtener configuración de dados.
        """
        super().__init__(data, message_sender)
        self.dice_handler = dice_handler
        self.session_data = session_data
        self.server_repo = server_repo

    async def execute(self) -> None:
        """Ejecuta la tirada de dados y envía el resultado al cliente (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar que tenemos el handler
        if not self.dice_handler:
            logger.error("DiceCommandHandler no disponible")
            return

        # Obtener valores mínimo y máximo desde Redis
        if self.server_repo:
            min_value = await self.server_repo.get_dice_min_value()
            max_value = await self.server_repo.get_dice_max_value()
        else:
            # Valores por defecto si no hay repositorio
            min_value = 6
            max_value = 18

        # Crear comando (solo datos)
        command = DiceCommand(min_value=min_value, max_value=max_value)

        # Delegar al handler (separación de responsabilidades)
        result = await self.dice_handler.handle(command)

        # Manejar resultado si es necesario
        if result.success and result.data and "attributes" in result.data:
            # Guardar atributos en session_data si está disponible
            if self.session_data is not None:
                self.session_data["dice_attributes"] = result.data["attributes"]
                logger.info(
                    "Atributos guardados en sesión para %s",
                    self.message_sender.connection.address,
                )
        elif not result.success:
            logger.debug("Tirada de dados falló: %s", result.error_message or "Error desconocido")
