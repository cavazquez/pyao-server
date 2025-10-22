"""Tarea para manejar el cambio de dirección del personaje."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.task import Task

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes para direcciones
HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4

# Constantes para validación de paquetes
MIN_CHANGE_HEADING_PACKET_SIZE = 2


class TaskChangeHeading(Task):
    """Tarea que maneja el cambio de dirección del personaje sin moverse."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        account_repo: AccountRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de cambio de dirección.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.session_data = session_data

    def _parse_packet(self) -> int | None:
        """Parsea el paquete de cambio de dirección.

        El formato esperado es:
        - Byte 0: PacketID (CHANGE_HEADING = 37)
        - Byte 1: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste)

        Returns:
            Dirección o None si hay error.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        heading = validator.read_heading()

        if validator.has_errors() or heading is None:
            return None

        return heading

    async def execute(self) -> None:
        """Ejecuta el cambio de dirección del personaje."""
        # Parsear dirección
        heading = self._parse_packet()
        if heading is None:
            logger.warning(
                "Paquete de cambio de dirección inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Verificar que el player_repo esté disponible
        if self.player_repo is None:
            logger.error("PlayerRepository no está disponible para cambio de dirección")
            return

        # Obtener user_id de la sesión
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de cambio de dirección sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Guardar la dirección en Redis
        await self.player_repo.set_heading(user_id, heading)

        logger.info(
            "User %d cambió dirección a %d",
            user_id,
            heading,
        )

        # Obtener datos visuales del personaje de Redis
        char_body = 1  # Valor por defecto
        char_head = 15  # Valor por defecto

        if self.account_repo and "username" in self.session_data:
            username = self.session_data["username"]
            if isinstance(username, str):
                account_data = await self.account_repo.get_account(username)
                if account_data:
                    char_body = int(account_data.get("char_race", 1))
                    char_head = int(account_data.get("char_head", 15))
                    # Si body es 0, usar valor por defecto
                    if char_body == 0:
                        char_body = 1

        # Enviar CHARACTER_CHANGE de vuelta al cliente para confirmar
        await self.message_sender.send_character_change(
            char_index=user_id,
            body=char_body,
            head=char_head,
            heading=heading,
        )

        # Broadcast multijugador: enviar CHARACTER_CHANGE a otros jugadores en el mapa
        if self.map_manager and self.player_repo:
            # Obtener el mapa actual del jugador
            position = await self.player_repo.get_position(user_id)
            if position:
                map_id = position["map"]

                # Enviar CHARACTER_CHANGE a todos los demás jugadores en el mapa
                other_senders = self.map_manager.get_all_message_senders_in_map(
                    map_id, exclude_user_id=user_id
                )
                for sender in other_senders:
                    await sender.send_character_change(
                        char_index=user_id,
                        body=char_body,
                        head=char_head,
                        heading=heading,
                    )

                logger.debug(
                    "Cambio de dirección de user %d notificado a %d jugadores en mapa %d",
                    user_id,
                    len(other_senders),
                    map_id,
                )
