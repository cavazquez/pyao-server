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
MIN_TALK_PACKET_SIZE = 3  # PacketID + int16


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


class TaskLogin(Task):
    """Tarea que maneja el login de usuarios."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de login.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            redis_client: Cliente Redis para verificar credenciales.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.redis_client = redis_client
        self.session_data = session_data

    def _parse_packet(self) -> tuple[str, str] | None:
        """Parsea el paquete de login.

        El formato esperado es:
        - Byte 0: PacketID (LOGIN)
        - Bytes 1-2: Longitud del username (int16, little-endian)
        - Bytes siguientes: Username (UTF-8)
        - Bytes siguientes (2): Longitud del password (int16, little-endian)
        - Bytes siguientes: Password (UTF-8)

        Returns:
            Tupla (username, password) o None si hay error.
        """
        try:
            offset = 1  # Saltar PacketID

            # Leer username
            if len(self.data) < offset + 2:
                return None
            username_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2

            if len(self.data) < offset + username_len:
                return None
            username = self.data[offset : offset + username_len].decode("utf-8")
            offset += username_len

            # Leer password
            if len(self.data) < offset + 2:
                return None
            password_len = int.from_bytes(
                self.data[offset : offset + 2],
                byteorder="little",
                signed=False,
            )
            offset += 2

            if len(self.data) < offset + password_len:
                return None
            password = self.data[offset : offset + password_len].decode("utf-8")

        except (ValueError, UnicodeDecodeError) as e:
            logger.warning("Error parseando paquete de login: %s", e)
            return None
        else:
            return (username, password)

    async def execute(self) -> None:
        """Ejecuta el login del usuario."""
        # Parsear datos del paquete
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete de login inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        username, password = parsed
        logger.info(
            "Intento de login desde %s - Username: %s",
            self.message_sender.connection.address,
            username,
        )

        # Verificar que Redis esté disponible
        if self.redis_client is None:
            logger.error("Redis no está disponible para login")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return

        # Verificar si la cuenta existe
        if not await self.redis_client.account_exists(username):
            logger.warning("Intento de login con usuario inexistente: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return

        # Obtener datos de la cuenta
        account_data = await self.redis_client.get_account_data(username)
        if not account_data:
            logger.error("Cuenta existe pero no se pudieron obtener datos: %s", username)
            await self.message_sender.send_error_msg("Error al obtener datos de cuenta")
            return

        # Verificar contraseña
        password_hash = self._hash_password(password)
        stored_hash = account_data.get("password_hash", "")

        if password_hash != stored_hash:
            logger.warning("Contraseña incorrecta para usuario: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return

        # Login exitoso
        user_id = int(account_data.get("user_id", 0))
        user_class = int(account_data.get("char_job", 1))  # Obtener clase del personaje
        logger.info("Login exitoso para %s (ID: %d, Clase: %d)", username, user_id, user_class)

        # Guardar user_id en session_data para uso posterior
        if self.session_data is not None:
            self.session_data["user_id"] = user_id  # type: ignore[assignment]
            logger.info("User ID %d guardado en sesión", user_id)

        # Enviar paquete Logged con la clase del personaje (protocolo AO estándar)
        await self.message_sender.send_logged(user_class)

        # Obtener y enviar posición del personaje
        position = await self.redis_client.get_player_position(user_id)

        if position is None:
            # Si no existe posición, crear una por defecto
            default_x = 50
            default_y = 50
            default_map = 1
            await self.redis_client.set_player_position(user_id, default_x, default_y, default_map)
            logger.info(
                "Posición inicial creada para user_id %d: (%d, %d) en mapa %d",
                user_id,
                default_x,
                default_y,
                default_map,
            )
            position = {"x": default_x, "y": default_y, "map": default_map}

        await self.message_sender.send_pos_update(position["x"], position["y"])
        logger.info(
            "Posición enviada: (%d, %d) en mapa %d",
            position["x"],
            position["y"],
            position["map"],
        )

    @staticmethod
    def _hash_password(password: str) -> str:
        """Genera un hash SHA-256 de la contraseña.

        Args:
            password: Contraseña en texto plano.

        Returns:
            Hash hexadecimal de la contraseña.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


class TaskRequestAttributes(Task):
    """Tarea que maneja la solicitud de atributos del personaje."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de solicitud de atributos.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            redis_client: Cliente Redis para obtener atributos.
            session_data: Datos de sesión compartidos (para obtener user_id).
        """
        super().__init__(data, message_sender)
        self.redis_client = redis_client
        self.session_data = session_data

    async def execute(self) -> None:
        """Obtiene atributos desde Redis y los envía al cliente usando PacketID 50."""
        # Primero verificar si hay atributos en sesión (creación de personaje)
        if self.session_data and "dice_attributes" in self.session_data:
            attributes = self.session_data["dice_attributes"]
            logger.info(
                "Enviando atributos desde sesión a %s: %s",
                self.message_sender.connection.address,
                attributes,
            )

            # Intentar con send_attributes (PacketID 50)
            await self.message_sender.send_attributes(
                strength=attributes["strength"],
                agility=attributes["agility"],
                intelligence=attributes["intelligence"],
                charisma=attributes["charisma"],
                constitution=attributes["constitution"],
            )
            return

        # Si no hay en sesión, obtener desde Redis usando user_id
        if not self.redis_client:
            logger.error("Redis no disponible para obtener atributos")
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        if not self.session_data or "user_id" not in self.session_data:
            logger.warning(
                "Cliente %s solicitó atributos pero no hay user_id en sesión",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        # Obtener atributos desde Redis
        user_id = self.session_data["user_id"]
        stats_key = f"player:{user_id}:stats"
        stats_data = await self.redis_client.redis.hgetall(stats_key)  # type: ignore[misc]

        if stats_data:
            strength = int(stats_data.get("strength", 0))
            agility = int(stats_data.get("agility", 0))
            intelligence = int(stats_data.get("intelligence", 0))
            charisma = int(stats_data.get("charisma", 0))
            constitution = int(stats_data.get("constitution", 0))

            logger.info(
                "Enviando atributos desde Redis para user_id %d: "
                "STR=%d AGI=%d INT=%d CHA=%d CON=%d",
                user_id,
                strength,
                agility,
                intelligence,
                charisma,
                constitution,
            )

            # Intentar con send_attributes (PacketID 50)
            await self.message_sender.send_attributes(
                strength=strength,
                agility=agility,
                intelligence=intelligence,
                charisma=charisma,
                constitution=constitution,
            )
        else:
            logger.warning(
                "No se encontraron atributos en Redis para user_id %d",
                user_id,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)


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

        # Verificar que Redis esté disponible
        if self.redis_client is None:
            logger.error("Redis no está disponible para crear cuenta")
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
            user_id = await self.redis_client.create_account(
                username=username,
                password_hash=password_hash,
                email=email,
                character_data=char_data or None,
                stats_data=stats_data or None,
            )

            logger.info(
                "Cuenta creada exitosamente: %s (ID: %d, Clase: %d) desde %s",
                username,
                user_id,
                char_data.get("job", 1) if char_data else 1,
                self.message_sender.connection.address,
            )

            # Crear posición inicial del personaje
            default_x = 50
            default_y = 50
            default_map = 1
            await self.redis_client.set_player_position(user_id, default_x, default_y, default_map)
            logger.info(
                "Posición inicial creada para nuevo personaje %s (ID: %d): (%d, %d) en mapa %d",
                username,
                user_id,
                default_x,
                default_y,
                default_map,
            )

            # Enviar paquete Logged con la clase del personaje (protocolo AO estándar)
            user_class = char_data.get("job", 1) if char_data else 1
            await self.message_sender.send_logged(user_class)

            # Enviar posición inicial
            await self.message_sender.send_pos_update(default_x, default_y)
            logger.info("Posición inicial enviada al nuevo personaje")

        except ValueError as e:
            # Cuenta ya existe u otro error de validación
            logger.warning("Error creando cuenta para %s: %s", username, e)
            await self.message_sender.send_error_msg(str(e))
        except Exception:
            logger.exception("Error inesperado creando cuenta para %s", username)
            await self.message_sender.send_error_msg("Error interno del servidor")


class TaskTalk(Task):
    """Tarea para procesar mensajes de chat del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Talk.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.session_data = session_data

    def _parse_packet(self) -> str | None:
        """Parsea el paquete Talk.

        Formato: PacketID (1 byte) + longitud (int16) + mensaje (string UTF-8)

        Returns:
            Mensaje de chat o None si el paquete es inválido.
        """
        try:
            if len(self.data) < MIN_TALK_PACKET_SIZE:
                return None

            # Leer longitud del mensaje (int16, little-endian)
            msg_length = int.from_bytes(self.data[1:3], byteorder="little", signed=False)

            # Verificar que hay suficientes bytes
            if len(self.data) < 3 + msg_length:
                return None

            # Leer y retornar mensaje
            return self.data[3 : 3 + msg_length].decode("utf-8")

        except (ValueError, UnicodeDecodeError):
            return None

    async def execute(self) -> None:
        """Procesa el mensaje de chat."""
        message = self._parse_packet()

        if message is None:
            logger.warning(
                "Paquete Talk inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Obtener user_id de la sesión
        user_id = None
        if self.session_data:
            user_id = self.session_data.get("user_id")

        if user_id is None:
            logger.warning(
                "Mensaje de chat recibido sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        logger.info(
            "Mensaje de chat de user_id %d: %s",
            user_id,
            message,
        )

        # Por ahora solo logueamos el mensaje
        # En el futuro se implementará broadcast a jugadores cercanos
