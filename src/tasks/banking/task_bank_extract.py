"""Tarea para extraer items del banco."""

import logging
from typing import TYPE_CHECKING

from src.commands.bank_extract_command import BankExtractCommand
from src.config.config_manager import ConfigManager, config_manager
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskBankExtract(Task):
    """Maneja la extracción de items del banco (solo parsing y delegación).

    Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        bank_extract_handler: BankExtractCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de extracción bancaria.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            bank_extract_handler: Handler para el comando de extraer item.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.bank_extract_handler = bank_extract_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta la extracción de un item del banco (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de extracción bancaria sin estar logueado")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        slot = validator.read_slot(
            min_slot=1,
            max_slot=ConfigManager.as_int(config_manager.get("game.bank.max_slots", 40)),
        )
        quantity = validator.read_quantity(min_qty=1, max_qty=10000)

        if validator.has_errors() or slot is None or quantity is None:
            error_msg = (
                validator.get_error_message() if validator.has_errors() else "Datos inválidos"
            )
            await self.message_sender.send_console_msg(error_msg)
            return

        # Validar que tenemos el handler
        if not self.bank_extract_handler:
            logger.error("BankExtractCommandHandler no disponible")
            await self.message_sender.send_console_msg("Error al extraer del banco")
            return

        # Crear comando (solo datos)
        command = BankExtractCommand(user_id=user_id, slot=slot, quantity=quantity)

        # Delegar al handler (separación de responsabilidades)
        result = await self.bank_extract_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success:
            logger.debug("Extraer item falló: %s", result.error_message or "Error desconocido")
