"""Tarea para creación de cuentas."""

import logging
from typing import TYPE_CHECKING

from src.commands.create_account_command import CreateAccountCommand
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.create_account_handler import CreateAccountCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 32


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
        self.session_data = session_data or {}

    def _parse_packet(self) -> tuple[str, str, str, dict[str, int]] | None:
        """Parsea el paquete de creación de cuenta.

        El formato esperado es:
        - Byte 0: PacketID (CREATE_ACCOUNT)
        - Bytes 1-2: Longitud del username (int16, little-endian)
        - Bytes siguientes: Username (UTF-8)
        - Bytes siguientes (2): Longitud del password (int16, little-endian)
        - Bytes siguientes: Password (UTF-8)
        - Byte siguiente: race (1 byte)
        - Bytes siguientes (2): Longitud de algo? (int16)
        - Byte siguiente: gender (1 byte)
        - Byte siguiente: class/job (1 byte)
        - Byte siguiente: ? (1 byte)
        - Bytes siguientes (2): head (int16)
        - Bytes siguientes (2): Longitud del email (int16, little-endian)
        - Bytes siguientes: Email (UTF-8)
        - Byte siguiente: home (1 byte)

        Returns:
            Tupla (username, password, email, char_data) o None si hay error.
        """
        try:
            # Usar PacketValidator para leer username y password
            # NOTA: task_account usa UTF-8, no UTF-16LE como otros packets
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)

            username = validator.read_string(
                min_length=MIN_USERNAME_LENGTH, max_length=MAX_USERNAME_LENGTH, encoding="utf-8"
            )
            password = validator.read_string(
                min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH, encoding="utf-8"
            )

            if validator.has_errors() or username is None or password is None:
                logger.warning(
                    "Error validando username/password: %s", validator.get_error_message()
                )
                return None

            logger.debug("Username: %s", username)
            logger.debug("Password parsed")

            # Actualizar offset para continuar leyendo datos del personaje
            offset = reader.offset

            # Leer datos del personaje (vienen antes del email)
            char_data = {}
            # Validar que haya suficientes bytes para los datos del personaje
            # Protocolo cliente (ver GameProtocol.WriteLoginNewChar):
            # [0, 13, 0] + race (u8) + gender (u8) + job (u8) + head (u16) noqa: ERA001
            if len(self.data) >= offset + 9:
                # Saltar los 3 bytes fijos (0, 13, 0)
                offset += 3

                char_data["race"] = self.data[offset]
                offset += 1

                char_data["gender"] = self.data[offset]
                offset += 1

                char_data["job"] = self.data[offset]
                offset += 1

                # Leer head (int16)
                char_data["head"] = int.from_bytes(
                    self.data[offset : offset + 2],
                    byteorder="little",
                    signed=False,
                )
                offset += 2
                logger.debug("Char data parsed, offset: %d", offset)

            # Leer email usando PacketValidator
            # Actualizar el reader al offset actual
            reader.offset = offset

            email = validator.read_string() if not validator.has_errors() else ""
            if email is None:
                email = ""
            offset = reader.offset
            logger.debug("Email: %s, offset: %d", email, offset)

            # Leer home (último byte) - validar que haya al menos 1 byte más
            # Leer home (último byte)
            if len(self.data) >= offset + 1:
                char_data["home"] = self.data[offset]
                logger.debug("Home: %d", char_data["home"])

        except (ValueError, UnicodeDecodeError) as e:
            logger.warning("Error parseando paquete de creación de cuenta: %s", e)
            return None
        else:
            return (username, password, email, char_data)

    async def execute(self) -> None:
        """Ejecuta la creación de cuenta (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        logger.info("TaskCreateAccount.execute() llamado")

        # Log de datos recibidos en hexadecimal para debugging
        hex_data = " ".join(f"{byte:02X}" for byte in self.data[:64])
        logger.info(
            "Datos recibidos para creación de cuenta (%d bytes): %s",
            len(self.data),
            hex_data,
        )

        # Parsear datos del paquete
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete de creación de cuenta inválido desde %s",
                self.message_sender.connection.address,
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
