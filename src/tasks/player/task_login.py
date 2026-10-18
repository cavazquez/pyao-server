"""Tarea que maneja el login de usuarios."""

import logging
from typing import TYPE_CHECKING

from src.commands.login_command import LoginCommand
from src.network.packet_reader import PacketReader
from src.network.validators.auth import LoginPacketValidator
from src.network.validators.base import ValidationContext
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.login_handler import LoginCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskLogin(Task):
    """Tarea que maneja el login de usuarios.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        login_handler: LoginCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de login.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            login_handler: Handler para el comando de login.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.login_handler = login_handler
        self.session_data = {} if session_data is None else session_data

    def _parse_packet(self) -> tuple[str, str] | None:
        """Lee las credenciales Latin-1 con los mismos límites del alta.

        Returns:
            Usuario y contraseña literales o None si están fuera del contrato.
        """
        result = LoginPacketValidator().validate(
            ValidationContext(reader=PacketReader(self.data), errors=[])
        )
        if not result.success or result.data is None:
            logger.warning("Formato de login inválido")
            return None
        return (result.data["username"], result.data["password"])

    async def execute(self) -> None:
        """Ejecuta el login del usuario (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Parsear datos del paquete
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete de login inválido desde %s",
                self.message_sender.address,
            )
            return

        username, password = parsed

        # Validar que tenemos el handler
        if not self.login_handler:
            logger.error("LoginCommandHandler no disponible")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return

        # Crear comando (solo datos)
        command = LoginCommand(username=username, password=password)

        # Delegar al handler (separación de responsabilidades)
        result = await self.login_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Login falló: %s", result.error_message or "Error desconocido")

    async def execute_with_credentials(self, username: str, password: str) -> None:
        """Ejecuta el login con credenciales ya parseadas.

        Este método se mantiene para compatibilidad con TaskCreateAccount
        que llama a login automático después de crear la cuenta.

        Args:
            username: Nombre de usuario.
            password: Contraseña en texto plano.
        """
        # Validar que tenemos el handler
        if not self.login_handler:
            logger.error("LoginCommandHandler no disponible")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return

        # Crear comando (solo datos)
        command = LoginCommand(username=username, password=password)

        # Delegar al handler (separación de responsabilidades)
        result = await self.login_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Login falló: %s", result.error_message or "Error desconocido")
