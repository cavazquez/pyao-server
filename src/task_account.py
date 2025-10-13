"""Tarea para creación de cuentas de usuario."""

import hashlib
import logging
from typing import TYPE_CHECKING

from src.task import Task
from src.task_login import TaskLogin

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6


class TaskCreateAccount(Task):
    """Tarea que maneja la creación de cuentas."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        account_repo: AccountRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de creación de cuenta.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.session_data = session_data

    def _parse_packet(self) -> tuple[str, str, str, dict[str, int]] | None:  # noqa: C901, PLR0915
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
            offset = 1  # Saltar PacketID

            # Leer username
            if len(self.data) < offset + 2:
                logger.warning("Paquete muy corto para leer longitud de username")
                return None
            username_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2
            logger.debug("Username length: %d, offset: %d", username_len, offset)

            if len(self.data) < offset + username_len:
                logger.warning(
                    "Paquete muy corto para leer username (esperado: %d, disponible: %d)",
                    username_len,
                    len(self.data) - offset,
                )
                return None
            username = self.data[offset : offset + username_len].decode("utf-8")
            offset += username_len
            logger.debug("Username: %s, offset: %d", username, offset)

            # Leer password
            if len(self.data) < offset + 2:
                logger.warning("Paquete muy corto para leer longitud de password")
                return None
            password_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2
            logger.debug("Password length: %d, offset: %d", password_len, offset)

            if len(self.data) < offset + password_len:
                logger.warning("Paquete muy corto para leer password")
                return None
            password = self.data[offset : offset + password_len].decode("utf-8")
            offset += password_len
            logger.debug("Password parsed, offset: %d", offset)

            # Leer datos del personaje (vienen antes del email)
            char_data = {}
            if len(self.data) >= offset + 8:
                char_data["race"] = self.data[offset]
                offset += 1

                # Saltar 2 bytes (int16 desconocido)
                offset += 2

                char_data["gender"] = self.data[offset]
                char_data["job"] = self.data[offset + 1]
                offset += 2

                # Saltar 1 byte desconocido
                offset += 1

                # Leer head (int16)
                char_data["head"] = int.from_bytes(
                    self.data[offset : offset + 2],
                    byteorder="little",
                    signed=False,
                )
                offset += 2
                logger.debug("Char data parsed, offset: %d", offset)

            # Leer email
            if len(self.data) < offset + 2:
                logger.warning("Paquete muy corto para leer longitud de email")
                return None
            email_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2
            logger.debug("Email length: %d, offset: %d", email_len, offset)

            if len(self.data) < offset + email_len:
                logger.warning("Paquete muy corto para leer email")
                return None
            email = self.data[offset : offset + email_len].decode("utf-8")
            offset += email_len
            logger.debug("Email: %s, offset: %d", email, offset)

            # Leer home (último byte)
            if len(self.data) >= offset + 1:
                char_data["home"] = self.data[offset]
                logger.debug("Home: %d", char_data["home"])

        except (ValueError, UnicodeDecodeError) as e:
            logger.warning("Error parseando paquete de creación de cuenta: %s", e)
            return None
        else:
            return (username, password, email, char_data)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Genera un hash SHA-256 de la contraseña.

        Args:
            password: Contraseña en texto plano.

        Returns:
            Hash hexadecimal de la contraseña.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    async def execute(self) -> None:
        """Ejecuta la creación de cuenta."""
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

        # Log de datos recibidos
        logger.info(
            "Solicitud de creación de cuenta desde %s - Username: %s, Email: %s, CharData: %s",
            self.message_sender.connection.address,
            username,
            email,
            char_data,
        )

        # Validar datos
        if not username or len(username) < MIN_USERNAME_LENGTH:
            logger.warning("Username muy corto: %s (len=%d)", username, len(username))
            await self.message_sender.send_error_msg(
                f"El nombre de usuario debe tener al menos {MIN_USERNAME_LENGTH} caracteres"
            )
            return

        if not password or len(password) < MIN_PASSWORD_LENGTH:
            logger.warning("Password muy corto: len=%d", len(password))
            await self.message_sender.send_error_msg(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
            )
            return

        if not email or "@" not in email:
            await self.message_sender.send_error_msg("Email inválido")
            return

        # Verificar que los repositorios estén disponibles
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para crear cuenta")
            await self.message_sender.send_error_msg("Servicio de cuentas no disponible")
            return

        # Hash de la contraseña
        password_hash = self._hash_password(password)

        # Obtener atributos de dados de la sesión
        stats_data = None
        if self.session_data and "dice_attributes" in self.session_data:
            stats_data = self.session_data["dice_attributes"]
            logger.info("Atributos de dados recuperados de sesión: %s", stats_data)
        else:
            logger.warning("No se encontraron atributos de dados en la sesión")

        # Crear cuenta en Redis con datos separados
        try:
            user_id = await self.account_repo.create_account(
                username=username,
                password_hash=password_hash,
                email=email,
                char_data=char_data,
            )

            logger.info(
                "Cuenta creada exitosamente: %s (ID: %d, Clase: %d) desde %s",
                username,
                user_id,
                char_data.get("job", 1) if char_data else 1,
                self.message_sender.connection.address,
            )

            # Guardar atributos de dados en Redis si existen
            if stats_data:
                await self.player_repo.set_attributes(
                    user_id=user_id,
                    strength=stats_data.get("strength", 10),
                    agility=stats_data.get("agility", 10),
                    intelligence=stats_data.get("intelligence", 10),
                    charisma=stats_data.get("charisma", 10),
                    constitution=stats_data.get("constitution", 10),
                )
                logger.info("Atributos guardados en Redis para user_id %d", user_id)

            # Ejecutar login automático después de crear la cuenta
            login_task = TaskLogin(
                data=self.data,
                message_sender=self.message_sender,
                player_repo=self.player_repo,
                account_repo=self.account_repo,
                session_data=self.session_data,
            )
            await login_task.execute_with_credentials(username, password)

        except ValueError as e:
            # Cuenta ya existe u otro error de validación
            logger.warning("Error creando cuenta para %s: %s", username, e)
            await self.message_sender.send_error_msg(str(e))
        except Exception:
            logger.exception("Error inesperado creando cuenta para %s", username)
            await self.message_sender.send_error_msg("Error interno del servidor")
