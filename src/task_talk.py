"""Tarea para mensajes de chat."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes
MIN_TALK_PACKET_SIZE = 3  # PacketID + int16
MAX_MESSAGE_LENGTH = 255  # Longitud máxima del mensaje de chat


class TaskTalk(Task):
    """Tarea para procesar mensajes de chat del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        account_repo: AccountRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea Talk.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            session_data: Datos de sesión del cliente.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
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

            reader = PacketReader(self.data)
            # Leer longitud del mensaje
            msg_length = reader.read_int16()

            # Validar longitud
            if msg_length < 1 or msg_length > MAX_MESSAGE_LENGTH:
                return None

            # Verificar que hay suficientes bytes
            if len(self.data) < 3 + msg_length:
                return None

            # Leer mensaje (UTF-8)
            message_bytes = self.data[3 : 3 + msg_length]
            return message_bytes.decode("utf-8")

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
        user_id = SessionManager.get_user_id(self.session_data)

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

        # Broadcast multijugador: enviar mensaje a todos los jugadores en el mapa
        if self.map_manager and self.player_repo and self.account_repo and self.session_data:
            # Obtener el nombre del usuario
            username = "Desconocido"
            if "username" in self.session_data:
                username_value = self.session_data["username"]
                if isinstance(username_value, str):
                    username = username_value

            # Convertir user_id a int
            if isinstance(user_id, dict):
                return

            user_id_int = int(user_id)

            # Obtener el mapa del jugador
            position = await self.player_repo.get_position(user_id_int)
            if position:
                map_id = position["map"]

                # Formatear mensaje con el nombre del usuario
                formatted_message = f"{username}: {message}"

                # Enviar a todos los jugadores en el mapa (incluyendo el emisor)
                all_senders = self.map_manager.get_all_message_senders_in_map(map_id)
                for sender in all_senders:
                    await sender.send_console_msg(formatted_message)

                logger.debug(
                    "Mensaje de chat de user %d enviado a %d jugadores en mapa %d",
                    user_id_int,
                    len(all_senders),
                    map_id,
                )
