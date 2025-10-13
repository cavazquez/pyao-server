"""Tarea para login de usuarios."""

import hashlib
import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskLogin(Task):
    """Tarea que maneja el login de usuarios."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        account_repo: AccountRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de login.

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
        await self.execute_with_credentials(username, password)

    async def execute_with_credentials(self, username: str, password: str) -> None:
        """Ejecuta el login con credenciales ya parseadas.

        Args:
            username: Nombre de usuario.
            password: Contraseña en texto plano.
        """
        logger.info(
            "Intento de login desde %s - Username: %s",
            self.message_sender.connection.address,
            username,
        )

        # Verificar que los repositorios estén disponibles
        if self.account_repo is None or self.player_repo is None:
            logger.error("Repositorios no están disponibles para login")
            await self.message_sender.send_error_msg("Servicio no disponible")
            return

        # Obtener datos de la cuenta
        account_data = await self.account_repo.get_account(username)
        if not account_data:
            logger.warning("Intento de login con usuario inexistente: %s", username)
            await self.message_sender.send_error_msg("Usuario o contraseña incorrectos")
            return

        # Verificar contraseña
        password_hash = self._hash_password(password)
        if not await self.account_repo.verify_password(username, password_hash):
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

        # Enviar paquete Logged con la clase del personaje
        await self.message_sender.send_logged(user_class)

        # Enviar índice del personaje en el servidor
        await self.message_sender.send_user_char_index_in_server(user_id)

        # Obtener y enviar posición del personaje
        position = await self.player_repo.get_position(user_id)

        if position is None:
            # Si no existe posición, crear una por defecto
            default_x = 50
            default_y = 50
            default_map = 1
            await self.player_repo.set_position(user_id, default_x, default_y, default_map)
            logger.info(
                "Posición inicial creada para user_id %d: (%d, %d) en mapa %d",
                user_id,
                default_x,
                default_y,
                default_map,
            )
            position = {"x": default_x, "y": default_y, "map": default_map}

        # Enviar cambio de mapa
        await self.message_sender.send_change_map(position["map"])

        # Obtener y enviar estadísticas completas del personaje
        user_stats = await self.player_repo.get_stats(user_id)

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
            await self.player_repo.set_stats(user_id=user_id, **user_stats)
            logger.info("Estadísticas por defecto creadas en Redis para user_id %d", user_id)

        await self.message_sender.send_update_user_stats(**user_stats)

        # Obtener y enviar hambre y sed
        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)

        if hunger_thirst is None:
            # Si no existen, crear valores por defecto
            hunger_thirst = {
                "max_water": 100,
                "min_water": 100,
                "max_hunger": 100,
                "min_hunger": 100,
            }
            await self.player_repo.set_hunger_thirst(user_id=user_id, **hunger_thirst)
            logger.info("Hambre y sed por defecto creadas en Redis para user_id %d", user_id)

        await self.message_sender.send_update_hunger_and_thirst(**hunger_thirst)

    @staticmethod
    def _hash_password(password: str) -> str:
        """Genera un hash SHA-256 de la contraseña.

        Args:
            password: Contraseña en texto plano.

        Returns:
            Hash hexadecimal de la contraseña.
        """
        return hashlib.sha256(password.encode("utf-8")).hexdigest()
