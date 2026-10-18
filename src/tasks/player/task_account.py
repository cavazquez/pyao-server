"""Tarea para creación de cuentas."""

import logging
from typing import TYPE_CHECKING

from src.commands.create_account_command import CreateAccountCommand
from src.network.packet_reader import PacketReader
from src.network.validators.auth import CreateAccountPacketValidator
from src.network.validators.base import ValidationContext
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.create_account_handler import CreateAccountCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskCreateAccount(Task):
    """Tarea que maneja la creación de cuentas.

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        create_account_handler: CreateAccountCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de creación de cuenta.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            create_account_handler: Handler para el comando de creación de cuenta.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.create_account_handler = create_account_handler
        self.session_data = {} if session_data is None else session_data

    def _parse_packet(self) -> tuple[str, str, str, dict[str, int]] | None:
        """Parsea una sola vez el layout u16/Latin-1 compartido de alta.

        Returns:
            Credenciales, email y selección literal, o None ante un payload inválido.
        """
        context = ValidationContext(reader=PacketReader(self.data), errors=[])
        result = CreateAccountPacketValidator().validate(context)
        if not result.success or result.data is None:
            logger.warning("Formato de alta inválido")
            return None
        data = result.data
        return (
            data["username"],
            data["password"],
            data["email"],
            {key: data[key] for key in ("race", "gender", "job", "head", "home")},
        )

    async def execute(self) -> None:
        """Ejecuta la creación de cuenta (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        logger.info("TaskCreateAccount.execute() llamado")

        logger.info(
            "Creación de cuenta: %d bytes desde %s", len(self.data), self.message_sender.address
        )

        # Parsear datos del paquete
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete de creación de cuenta inválido desde %s",
                self.message_sender.address,
            )
            await self.message_sender.send_error_msg("Formato de paquete inválido")
            return

        username, password, email, char_data = parsed

        # Validar que tenemos el handler
        if not self.create_account_handler:
            logger.error("CreateAccountCommandHandler no disponible")
            await self.message_sender.send_error_msg("Servicio de cuentas no disponible")
            return

        # Crear comando (solo datos)
        command = CreateAccountCommand(
            username=username,
            password=password,
            email=email,
            char_data=char_data,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.create_account_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug(
                "Creación de cuenta falló: %s", result.error_message or "Error desconocido"
            )
            if result.error_message:
                await self.message_sender.send_error_msg(result.error_message)
