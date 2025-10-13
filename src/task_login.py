"""Tarea para login de usuarios."""

import hashlib
import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


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

        # Enviar paquete Logged (solo PacketID, sin datos)
        await self.message_sender.send_logged()
        logger.info("Paquete LOGGED enviado para user_id %d", user_id)

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
            "Paquete POS_UPDATE enviado: (%d, %d) en mapa %d",
            position["x"],
            position["y"],
            position["map"],
        )

        # Obtener y enviar estadísticas completas del personaje
        user_stats = await self.redis_client.get_player_user_stats(user_id)

        if user_stats is None:
            # Si no existen stats, crear valores por defecto
            user_stats = {
                "max_hp": 100,
                "min_hp": 100,
                "max_mana": 100,
                "min_mana": 100,
                "max_sta": 100,
                "min_sta": 100,
                "gold": 0,
                "level": 1,
                "elu": 300,
                "experience": 0,
            }
            await self.redis_client.set_player_user_stats(user_id=user_id, **user_stats)
            logger.info("Estadísticas por defecto creadas en Redis para user_id %d", user_id)

        await self.message_sender.send_update_user_stats(**user_stats)
        logger.info("Paquete UPDATE_USER_STATS enviado para user_id %d", user_id)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Genera un hash SHA-256 de la contraseña.

        Args:
            password: Contraseña en texto plano.

        Returns:
            Hash hexadecimal de la contraseña.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
