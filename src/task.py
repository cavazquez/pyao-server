"""Sistema de tareas para procesar mensajes del cliente."""

import hashlib
import logging
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Constantes de validación
MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6


class Task(ABC):
    """Clase base para tareas que procesan mensajes del cliente."""

    def __init__(self, data: bytes, message_sender: MessageSender) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
        """
        self.data = data
        self.message_sender = message_sender

    @abstractmethod
    async def execute(self) -> None:
        """Ejecuta la tarea. Debe ser implementado por las subclases."""
        ...


class TaskNull(Task):
    """Tarea que se ejecuta cuando no se reconoce el mensaje."""

    async def execute(self) -> None:
        """Loguea información detallada del mensaje no reconocido."""
        logger.warning(
            "Mensaje no reconocido desde %s - Tamaño: %d bytes",
            self.message_sender.connection.address,
            len(self.data),
        )

        # Mostrar los primeros bytes en hexadecimal
        hex_preview = " ".join(f"{byte:02X}" for byte in self.data[:32])
        logger.warning("Primeros bytes (hex): %s", hex_preview)

        # Mostrar el primer byte como posible PacketID
        if len(self.data) > 0:
            packet_id = self.data[0]
            logger.warning("Posible PacketID: %d (0x%02X)", packet_id, packet_id)

        # Mostrar representación ASCII (caracteres imprimibles)
        ascii_min = 32
        ascii_max = 127
        ascii_repr = "".join(
            chr(byte) if ascii_min <= byte < ascii_max else "." for byte in self.data[:64]
        )
        logger.warning("Representación ASCII: %s", ascii_repr)


class TaskDice(Task):
    """Tarea que maneja la tirada de dados."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de tirada de dados.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.session_data = session_data

    async def execute(self) -> None:
        """Ejecuta la tirada de dados y envía el resultado al cliente."""
        # Tirar 5 atributos (Fuerza, Agilidad, Inteligencia, Carisma, Constitución)
        strength = random.randint(6, 18)  # noqa: S311
        agility = random.randint(6, 18)  # noqa: S311
        intelligence = random.randint(6, 18)  # noqa: S311
        charisma = random.randint(6, 18)  # noqa: S311
        constitution = random.randint(6, 18)  # noqa: S311

        logger.info(
            "Cliente %s tiró dados - STR:%d AGI:%d INT:%d CHA:%d CON:%d",
            self.message_sender.connection.address,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )

        # Guardar atributos en session_data si está disponible
        if self.session_data is not None:
            self.session_data["dice_attributes"] = {
                "strength": strength,
                "agility": agility,
                "intelligence": intelligence,
                "charisma": charisma,
                "constitution": constitution,
            }
            logger.info(
                "Atributos guardados en sesión para %s",
                self.message_sender.connection.address,
            )

        # Enviar resultado usando el enviador de mensajes
        await self.message_sender.send_dice_roll(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )

        logger.info("Enviado resultado de dados a %s", self.message_sender.connection.address)


class TaskCreateAccount(Task):
    """Tarea que maneja la creación de cuentas."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de creación de cuenta.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            redis_client: Cliente Redis para almacenar la cuenta (opcional).
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.redis_client = redis_client
        self.session_data = session_data

    def _parse_packet(self) -> tuple[str, str, str, dict[str, int]] | None:  # noqa: PLR0911, C901, PLR0915
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
            await self.message_sender.send_account_error("Formato de paquete inválido")
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
            await self.message_sender.send_account_error(
                f"El nombre de usuario debe tener al menos {MIN_USERNAME_LENGTH} caracteres"
            )
            return

        if not password or len(password) < MIN_PASSWORD_LENGTH:
            logger.warning("Password muy corto: len=%d", len(password))
            await self.message_sender.send_account_error(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
            )
            return

        if not email or "@" not in email:
            await self.message_sender.send_account_error("Email inválido")
            return

        # Verificar que Redis esté disponible
        if self.redis_client is None:
            logger.error("Redis no está disponible para crear cuenta")
            await self.message_sender.send_account_error("Servicio de cuentas no disponible")
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
            user_id = await self.redis_client.create_account(
                username=username,
                password_hash=password_hash,
                email=email,
                character_data=char_data or None,
                stats_data=stats_data or None,
            )

            logger.info(
                "Cuenta creada exitosamente: %s (ID: %d) desde %s",
                username,
                user_id,
                self.message_sender.connection.address,
            )

            # Enviar confirmación al cliente
            await self.message_sender.send_account_created(user_id)

        except ValueError as e:
            # Cuenta ya existe u otro error de validación
            logger.warning("Error creando cuenta para %s: %s", username, e)
            await self.message_sender.send_account_error(str(e))
        except Exception:
            logger.exception("Error inesperado creando cuenta para %s", username)
            await self.message_sender.send_account_error("Error interno del servidor")
